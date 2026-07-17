# Requirements Document

## Introduction

Burn-Ex Cloud is a hosted, multi-user fitness analytics web application. Users authenticate with their Google account via Firebase Auth, then access real-time posture correction, rep counting, and calorie estimation from any browser. Pose detection runs entirely in the browser using MediaPipe's JS/WASM build (`@mediapipe/tasks-vision`) — no video frames leave the device. Only lightweight landmark coordinates are transmitted to the FastAPI backend (hosted on Render) over an authenticated WebSocket for ML inference, calorie calculation, and persistence. All user data is stored in PostgreSQL (Supabase) and scoped exclusively to the authenticated user's Firebase UID.

### Out of Scope

The following are explicitly excluded from this version and shall not be implemented:

| Excluded Feature | Reason |
|---|---|
| Offline / local network operation | Application requires Firebase Auth and the Render backend; internet connectivity is required |
| Model retraining or continuous learning | The Random Forest classifier and MET configs are static; no training pipeline or user-data retention for ML purposes |
| Unauthenticated access mode | Firebase Auth is required; there is no local bypass or guest mode |
| External AI APIs (OpenAI, Google Vision, etc.) | All ML inference uses the static local model only |
| Native mobile app (iOS/Android) | Browser-based access via Firebase Hosting is sufficient |
| Social features (sharing, leaderboards) | Out of scope for this version |
| Video recording or playback | Frames are processed in-browser only and are never transmitted or stored |
| Wearable device integration | No hardware dependencies beyond webcam |
| Nutrition tracking or diet planning | Calorie burn only; intake is out of scope |

---

## Glossary

| Term | Definition |
|---|---|
| `firebase_uid` | The immutable unique identifier assigned to a user by Firebase Auth; used as the tenant key throughout the system |
| ID token | A short-lived Firebase JWT issued to the authenticated client after sign-in; must be attached to every backend request |
| WebSocket session | The persistent `/ws/pose` connection established per active workout session |
| Active session | A workout session with `status = "active"` belonging to the currently authenticated user |
| Landmark frame | A JSON payload of 33 normalized MediaPipe pose coordinates (x, y, z, visibility) transmitted from the browser to the backend |
| Render cold-start | The ~30–60 second delay caused by the Render free-tier instance spinning up after ~15 minutes of inactivity |
| CORS | Cross-Origin Resource Sharing; the browser mechanism enforcing that the Render backend only accepts requests from the Firebase Hosting origin |

---

## Requirements

### Requirement 1: Firebase Authentication

**User Story:** As a user, I want to sign in with my Google account so that my workout data is securely tied to my identity and accessible from any device.

#### Acceptance Criteria

1. WHEN a user navigates to the application, THE SYSTEM SHALL present a sign-in screen and SHALL NOT grant access to any workout, history, or profile functionality until the user has successfully authenticated via Firebase Auth with Google Sign-In.
2. WHEN the user completes Google Sign-In, THE SYSTEM SHALL obtain a Firebase ID token from the Firebase Auth SDK and store it in memory for the duration of the browser session (not in `localStorage` or cookies accessible to third-party scripts).
3. WHEN the frontend makes any REST API request to the backend, THE SYSTEM SHALL attach the current Firebase ID token as the value of the `Authorization: Bearer <token>` header.
4. WHEN the backend receives any REST API request, THE SYSTEM SHALL verify the `Authorization` header token using the Firebase Admin SDK before processing the request; if the token is absent, expired, or invalid, THE SYSTEM SHALL return HTTP 401 and SHALL NOT process the request.
5. WHEN the frontend establishes a WebSocket connection to `/ws/pose`, THE SYSTEM SHALL transmit the current Firebase ID token in the initial handshake message before sending any landmark frames.
6. WHEN the backend receives a WebSocket connection to `/ws/pose`, THE SYSTEM SHALL verify the token from the handshake message using the Firebase Admin SDK; if the token is absent, expired, or invalid, THE SYSTEM SHALL close the connection with WebSocket close code `4001` and SHALL NOT process any subsequent messages on that connection.
7. WHEN a Firebase ID token expires while a WebSocket connection is active, THE SYSTEM SHALL allow the frontend to send a token-refresh message over the existing connection and verify the refreshed token; if the refresh succeeds, THE SYSTEM SHALL continue the session uninterrupted. IF the refresh fails for any reason (expired refresh token, account disabled, network error), THE SYSTEM SHALL immediately persist the active session as interrupted (identical to the interrupted-session path in Requirement 8, criterion 3), close the WebSocket connection with close code `4001`, and redirect the user to the sign-in screen. No grace period is permitted after a failed refresh — continued landmark processing without a verified identity is not allowed. *Rationale: Firebase ID tokens expire every hour; a successful refresh avoids disrupting an active workout, but a failed refresh means the identity can no longer be verified and the session must be treated as interrupted rather than continuing unauthenticated.*
8. WHEN the user signs out, THE SYSTEM SHALL immediately revoke the in-memory ID token reference, close any active WebSocket connection, persist any active session as interrupted, and redirect the user to the sign-in screen.
9. WHEN the user's Google account authentication state changes to signed-out (e.g., sign-out from another tab or account disablement), THE SYSTEM SHALL detect the change via the Firebase Auth SDK's `onAuthStateChanged` listener, close any active WebSocket connection, persist any active session as interrupted, and redirect to the sign-in screen as soon as the state change is received by the listener. No fixed propagation delay is guaranteed or required — the requirement is that the app responds to the event when the SDK delivers it. *Rationale: `onAuthStateChanged` propagation latency across devices and tabs is not bounded by the Firebase SDK; a hard time-bound SLA is not enforceable or testable. The security guarantee is event-driven responsiveness, not a wall-clock deadline.*
10. WHEN an authenticated user's token is verified, THE SYSTEM SHALL extract the `firebase_uid` from the token claims and use it as the sole user identity key for all database reads and writes in that request lifecycle.

---

### Requirement 2: Multi-Tenancy and Data Isolation

**User Story:** As a user, I want my workout data to be completely private and isolated from other users so that no one else can view or modify my sessions, history, or profile.

#### Acceptance Criteria

1. WHEN any database query reads or writes rows in the `sessions`, `sets`, `form_score_samples`, `calorie_segments`, `goals`, or `streaks` tables, THE SYSTEM SHALL scope the query to the authenticated user's `firebase_uid`; cross-user queries are prohibited.
2. WHEN a user requests a resource by ID and the resource's `user_id` does not match the authenticated user's `firebase_uid`, THE SYSTEM SHALL return HTTP 404, revealing no information about the existence of another user's resource. WHEN a user requests an operation on their own resource that is not permitted in the current state (e.g., modifying a completed session, changing weight during an active session), THE SYSTEM SHALL return HTTP 403. *Rationale: 404 prevents user enumeration — a 403 would confirm the resource exists. 403 is reserved for permission failures on resources the requester legitimately owns, where confirming existence is not a security concern.*
3. WHEN multiple authenticated users start concurrent workout sessions, THE SYSTEM SHALL handle each session independently with no shared mutable state between users' session objects, rep counters, or calorie accumulators.
4. WHEN a user attempts to start a second session while one is already active under their `firebase_uid`, THE SYSTEM SHALL return HTTP 409 and prompt the user to end or recover the existing session.
5. WHEN the backend writes a new row to any user-owned table, THE SYSTEM SHALL always populate the `user_id` column from the verified `firebase_uid` in the current request's token; client-supplied `user_id` values in request bodies SHALL be ignored. *Rationale: Accepting client-supplied user IDs would allow a user to write data under another user's UID.*

---

### Requirement 3: Browser-Side Pose Detection

**User Story:** As a user, I want the app to detect my pose in real time using my camera so that I receive immediate feedback on my form and rep count, without my video ever leaving my device.

#### Acceptance Criteria

1. WHEN the user grants camera permission and starts a session, THE SYSTEM SHALL initialize the MediaPipe Tasks Vision pose landmarker (`@mediapipe/tasks-vision`) in the browser and begin extracting 33 normalized landmark coordinates (x, y, z, visibility) from the live webcam feed at a minimum of 15 frames per second.
2. WHILE a session is active, THE SYSTEM SHALL run MediaPipe inference in the browser and SHALL NOT transmit raw video frames or encoded image data to the backend at any point. *Rationale: Transmitting video frames violates the privacy guarantee and would saturate the Render free-tier connection; inference is already complete in the browser.*
3. WHILE a session is active, THE SYSTEM SHALL package each extracted landmark set into a landmark frame payload and transmit it to the backend over the authenticated WebSocket with an end-to-end latency (browser inference + network transmission + server response) of no more than 300 ms. *Rationale: Browser-side inference on lower-end devices adds ~50–100 ms over the previous server-side budget; 300 ms keeps feedback perceptibly real-time.*
4. WHEN a landmark's visibility score falls below 0.5, THE SYSTEM SHALL mark that landmark as low-confidence and the backend SHALL exclude it from form scoring and correction calculations for that frame.
5. WHEN more than 30% of the landmarks required for the active exercise are simultaneously low-confidence in a frame, THE SYSTEM SHALL surface a "Move into frame" warning to the user and suspend form scoring until confidence recovers.
6. WHEN camera access is denied or no camera device is available, THE SYSTEM SHALL display a clear error message and SHALL prevent session start.
7. WHEN more than one person is detected within the camera frame, THE SYSTEM SHALL transmit only the landmark set with the largest bounding box (nearest person) and SHALL exclude all other detected persons' landmarks from the payload sent to the backend.
8. WHEN the MediaPipe WASM model files fail to load on initial page load, THE SYSTEM SHALL display an error message indicating that pose detection could not be initialized and SHALL prevent session start until the model files are successfully loaded.
9. WHEN the browser tab is hidden while a session is active, THE SYSTEM SHALL notify the user that moving away from the tab may degrade detection quality.

---

### Requirement 4: Exercise Classification

**User Story:** As a user, I want the system to automatically identify which exercise I am performing so that I receive exercise-specific feedback without manually selecting an exercise type.

*Note: Server-side classification logic is unchanged from the validated implementation. The input source change is that landmarks arrive pre-computed from the browser rather than being extracted server-side from raw frames.*

#### Acceptance Criteria

1. WHEN a landmark frame is received by the backend over the authenticated WebSocket, THE SYSTEM SHALL classify the current exercise from the supported set: squat, push-up, lunge, bicep curl, shoulder press, and plank.
2. WHEN the classifier's confidence for the top-predicted exercise type is below 0.6, THE SYSTEM SHALL treat the exercise as unrecognized and SHALL NOT update the active exercise label for that frame.
3. WHEN the exercise has been unrecognized for more than 3 consecutive seconds, THE SYSTEM SHALL send an "Exercise not recognized — adjust position" message to the client over the WebSocket.
4. WHEN the classified exercise type changes from the previously confirmed type with confidence ≥ 0.6 sustained for at least 10 consecutive frames, THE SYSTEM SHALL update the active exercise label, close the current set, and begin a new set under the new exercise type. *Rationale: Requiring sustained confidence prevents spurious exercise switches mid-rep.*
5. WHILE a session is active, THE SYSTEM SHALL maintain the last confirmed exercise type as the active type until a new type is confirmed or the session ends.

---

### Requirement 5: Posture and Form Correction

**User Story:** As a user, I want to receive specific, actionable corrective cues during my workout so that I can improve my form in real time and reduce injury risk.

*Note: Server-side form scoring logic and angle thresholds are unchanged. Input source change: the backend receives pre-extracted landmarks, not raw frames.*

#### Acceptance Criteria

1. WHILE a session is active and an exercise type is confirmed, THE SYSTEM SHALL evaluate joint angles relevant to that exercise on every received landmark frame.
2. WHEN a joint angle deviates from the acceptable range defined for the active exercise, THE SYSTEM SHALL generate a specific corrective cue (e.g., "Drive knees out", "Keep chest up") rather than a generic warning. *Rationale: Exercise-specific cues are actionable; generic alerts do not guide correction.*
3. WHEN multiple joint angle violations are detected in the same frame, THE SYSTEM SHALL prioritize and surface no more than 2 corrective cues at a time, ordered by severity. *Rationale: Displaying too many simultaneous cues overwhelms the user during an active rep.*
4. WHEN the user's form is within all acceptable joint angle ranges for the active exercise, THE SYSTEM SHALL include a positive form indicator in the analysis result and assign a form score of 100 for that frame.
5. WHILE a session is active, THE SYSTEM SHALL compute a rolling form score (0–100) per frame based on the proportion and magnitude of joint angle violations and SHALL maintain a per-set average form score.
6. WHEN required landmarks are low-confidence for a frame, THE SYSTEM SHALL suspend corrective cue generation for that frame and the client SHALL display only the "Move into frame" warning.
7. WHEN a plank is the active exercise, THE SYSTEM SHALL evaluate form on a time basis (hold duration and body alignment) and generate cues specific to static hold exercises (e.g., "Drop hips slightly", "Engage core").

---

### Requirement 6: Rep Counting

**User Story:** As a user, I want the system to automatically count my reps and detect set boundaries so that I have an accurate record of my workout volume without manually tracking.

*Note: Counting logic is unchanged. Angle sequences are derived from browser-extracted landmarks.*

#### Acceptance Criteria

1. WHILE a session is active and an exercise type is confirmed, THE SYSTEM SHALL count a completed rep when the relevant joint angle sequence completes one full concentric–eccentric cycle within the defined angle thresholds for the active exercise.
2. WHEN a joint angle cycle does not reach the minimum range of motion threshold, THE SYSTEM SHALL NOT count it as a completed rep. *Rationale: Partial reps must not inflate rep counts or calorie estimates.*
3. WHEN a rep is counted, THE SYSTEM SHALL increment the rep counter for the current set and include the updated count in the next analysis result sent to the client.
4. WHEN the user pauses movement for more than 8 seconds after completing at least one rep, THE SYSTEM SHALL automatically close the current set, record it with its rep count and average form score, and prepare a new set.
5. WHEN the exercise type changes, THE SYSTEM SHALL close the current set before opening a new set under the new exercise type.
6. WHILE a session is active, THE SYSTEM SHALL track the total rep count across all sets and the per-set rep counts independently.
7. WHEN a plank is the active exercise, THE SYSTEM SHALL track hold duration in seconds rather than rep count and include it in the analysis result sent to the client.

---

### Requirement 7: Calorie Estimation

**User Story:** As a user, I want to see an accurate estimate of calories burned during my workout so that I can track my energy expenditure over time.

*Note: MET calculation logic is unchanged. The weight source is now the authenticated user's profile in PostgreSQL.*

#### Acceptance Criteria

1. WHILE a session is active with a confirmed exercise type and a weight stored in the authenticated user's profile, THE SYSTEM SHALL continuously estimate calories burned using `Calories = MET × weight_kg × duration_hours`, where MET is the value assigned to the confirmed exercise type.
2. WHEN an authenticated user has not set their weight in their profile, THE SYSTEM SHALL block session start and prompt the user to set their weight before proceeding.
3. WHEN the active exercise type changes mid-session, THE SYSTEM SHALL freeze the calorie total accumulated under the previous exercise type and begin accumulating calories using the MET value for the new exercise type from the point of change.
4. WHEN a session ends, THE SYSTEM SHALL record the total calories burned as the sum of all per-exercise-type calorie segments and persist it to the authenticated user's session record in PostgreSQL.
5. WHILE a session is active, THE SYSTEM SHALL include the running calorie estimate in analysis results sent to the client, updated at least once every 5 seconds.
6. WHEN the user updates their weight in their profile between sessions, THE SYSTEM SHALL use the updated weight for all future sessions and SHALL NOT retroactively recalculate calories for completed sessions.

---

### Requirement 8: Session Management

**User Story:** As a user, I want my workout sessions to be reliably saved to my account so that I never lose workout data due to connection drops or page refreshes.

#### Acceptance Criteria

1. WHEN an authenticated user initiates a session start action and their weight is set in their profile, THE SYSTEM SHALL create a new session record scoped to the user's `firebase_uid`, begin accepting landmark frames over the authenticated WebSocket, and return the new `session_id` to the client.
2. WHEN the user initiates a session end action, THE SYSTEM SHALL stop accepting landmark frames, finalize all calorie and rep calculations, persist the complete session record to PostgreSQL under the user's `firebase_uid`, close the WebSocket connection gracefully, and return the session summary to the client.
3. WHEN the WebSocket connection drops while a session is active (browser tab closed, network interruption, or Render instance restart), THE SYSTEM SHALL persist a partial session record to PostgreSQL with all data accumulated to that point, marked with `status = "interrupted"`. *Rationale: Data accumulated up to interruption has value for history and streak tracking.*
4. WHEN an authenticated user opens the application and a session with `status = "interrupted"` exists for their `firebase_uid` with a `last_updated` timestamp within the past 24 hours, THE SYSTEM SHALL display a notification offering to resume or discard the interrupted session before allowing a new session to start.
5. WHEN the user chooses to resume an interrupted session, THE SYSTEM SHALL reopen the session (set `status = "active"`), restore the accumulated rep counts, calorie total, and set history to the client, and resume the WebSocket connection.
6. WHILE a session is active, THE SYSTEM SHALL persist incremental session state (rep counts, calorie total, current form scores) to PostgreSQL at intervals of no more than 30 seconds, so that a connection drop loses at most 30 seconds of data.
7. WHEN an authenticated user attempts to start a new session while one is already active under their `firebase_uid`, THE SYSTEM SHALL return HTTP 409 and present the user with options to end the existing session or resume it.

---

### Requirement 9: History and Progress Tracking

**User Story:** As a user, I want to view my workout history and progress trends so that I can see how my fitness and form are improving over time.

*Note: Conceptually unchanged; queries are now scoped per authenticated user rather than reading all rows from a single-user database.*

#### Acceptance Criteria

1. WHEN an authenticated user navigates to the session history view, THE SYSTEM SHALL retrieve and display all completed and interrupted sessions belonging to their `firebase_uid`, ordered by most recent first.
2. WHEN the user selects a past session, THE SYSTEM SHALL display the session's exercise type, total reps, sets, calories burned, duration, average form score, and per-set form score trend.
3. WHEN the user views their progress dashboard, THE SYSTEM SHALL display a time-series chart of calories burned per session over the most recent 30 sessions belonging to their `firebase_uid`.
4. WHEN the user views their progress dashboard, THE SYSTEM SHALL display the average form score trend across the most recent 10 sessions for each exercise type that has at least 2 recorded sessions under their `firebase_uid`.
5. WHILE the user has at least one completed session on each of N consecutive calendar days (evaluated in UTC), THE SYSTEM SHALL record and display a streak of N days for their account.
6. WHEN the user's streak is broken (no completed session on a calendar day), THE SYSTEM SHALL reset the streak counter to 0 and retain the historical best streak for display.
7. WHEN the user sets a daily or weekly calorie goal, THE SYSTEM SHALL track progress toward that goal using completed session calorie totals belonging to their `firebase_uid` and display the current progress.
8. WHEN a daily calorie goal is met, THE SYSTEM SHALL display a goal-achieved notification for that day.

---

### Requirement 10: Hosted Infrastructure Behavior

**User Story:** As a user, I want the app to communicate clearly when the server is starting up so that I understand why there is a delay and do not think the app is broken.

#### Acceptance Criteria

1. WHEN the frontend attempts to connect to the Render-hosted backend and the backend does not respond within 10 seconds, THE SYSTEM SHALL display a "Waking up the server — this may take up to 60 seconds on first connection" loading indicator rather than a generic network error. *Rationale: The Render free tier spins down after ~15 minutes of inactivity; the ~30–60 second cold-start must be communicated rather than appear as a failure.*
2. WHEN the backend becomes reachable after a cold-start delay, THE SYSTEM SHALL automatically proceed with the pending connection or request without requiring the user to manually retry.
3. WHEN the backend receives any HTTP or WebSocket request from a browser origin that is not the configured Firebase Hosting domain, THE SYSTEM SHALL reject the request with HTTP 403 and SHALL NOT process it. *Rationale: Requests carry real authenticated tokens; a wildcard CORS policy would allow any origin to relay those tokens.*
4. THE SYSTEM SHALL serve all frontend traffic exclusively over HTTPS (enforced by Firebase Hosting) and all backend API traffic exclusively over HTTPS/WSS (enforced by Render); plain HTTP or WS connections SHALL NOT be accepted in production.
5. WHEN the frontend is deployed to Firebase Hosting, THE SYSTEM SHALL serve all static assets including the MediaPipe WASM model files from Firebase Hosting's CDN with no runtime dependency on any other external origin. *Rationale: Serving MediaPipe WASM from Firebase Hosting ensures the model loads reliably and avoids a second origin dependency.*
6. WHEN the Render-hosted backend instance restarts or is replaced during a deployment, THE SYSTEM SHALL treat any active WebSocket connections as interrupted and the interrupted-session persistence behavior SHALL apply.

---

### Requirement 11: User Profile

**User Story:** As a user, I want my profile (weight, display name) to be tied to my Google account so that my calorie estimates are accurate and my preferences are available on any device I sign in from.

#### Acceptance Criteria

1. WHEN a user authenticates with Firebase Auth for the first time and no profile record exists for their `firebase_uid`, THE SYSTEM SHALL automatically create a profile record in PostgreSQL and prompt the user to enter their weight in kilograms before any session can be started.
2. WHEN the user submits a weight value that is not a positive number between 20 kg and 300 kg, THE SYSTEM SHALL reject the input and display a validation error message.
3. WHEN the user returns to the application and a profile with a valid weight already exists for their `firebase_uid`, THE SYSTEM SHALL not prompt for weight again unless the weight field has been explicitly cleared.
4. WHEN the user updates their display name in their profile, THE SYSTEM SHALL persist the change to PostgreSQL under their `firebase_uid` and reflect the updated name throughout the application immediately.
5. WHEN the user attempts to update their weight while a session is active under their `firebase_uid`, THE SYSTEM SHALL return HTTP 403, display a message that weight cannot be changed during an active session, and preserve the weight recorded at session start for that session's calorie calculations. *Rationale: The user owns the profile but the operation is not permitted in the current state — this is a 403, not a 409, per the ownership/permission distinction in Requirement 2.*
6. WHEN the user updates their weight between sessions, THE SYSTEM SHALL store the new weight in their profile and use it for all subsequent sessions.
7. WHEN a different Google account signs in on the same device, THE SYSTEM SHALL load only the profile, session history, goals, and streaks belonging to the newly signed-in account's `firebase_uid`, with no data visible from the previous account.
