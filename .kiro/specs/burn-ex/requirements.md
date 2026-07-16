# Burn-Ex — Requirements

> **Spec stage:** Requirements  
> **Notation:** EARS (Easy Approach to Requirements Syntax)  
> **Source of truth:** `.kiro/steering/burn-ex-project.md`  
> **Out-of-scope items are not represented here.** Refer to the steering document for the explicit exclusion list.

---

## 1. Pose Detection

**REQ-1.1**  
WHEN the user grants camera permission and starts a session, THE SYSTEM SHALL begin extracting MediaPipe Pose landmarks from the live webcam feed at a minimum of 15 frames per second.  
*Rationale: 15 FPS is the minimum for feedback to feel real-time during exercise; lower rates cause perceptible lag in correction cues.*

**REQ-1.2**  
WHILE a session is active, THE SYSTEM SHALL process each captured frame and produce a set of 33 normalized landmark coordinates (x, y, z, visibility) before advancing to the next pipeline stage.

**REQ-1.3**  
WHEN a landmark's visibility score falls below 0.5, THE SYSTEM SHALL mark that landmark as low-confidence and exclude it from form scoring and correction calculations for that frame.  
*Rationale: Using occluded landmarks produces incorrect joint angle readings and misleading correction cues.*

**REQ-1.4**  
WHEN more than 30% of the required landmarks for the active exercise are simultaneously low-confidence, THE SYSTEM SHALL surface a "Move into frame" warning to the user and suspend form scoring until confidence recovers.

**REQ-1.5**  
WHILE a session is active, THE SYSTEM SHALL deliver processed landmark data to the exercise classification and form correction modules with an end-to-end latency of no more than 200 ms from frame capture to feedback display.  
*Rationale: Feedback beyond 200 ms is perceived as disconnected from the physical movement.*

**REQ-1.6**  
WHEN camera access is denied or the camera device is unavailable, THE SYSTEM SHALL display a clear error message explaining that camera access is required and prevent session start.

**REQ-1.7**  
WHEN more than one person is detected within the camera frame, THE SYSTEM SHALL identify the person whose pose landmarks are largest/closest to the camera (based on landmark bounding-box size or estimated proximity) as the active user, and SHALL exclude all other detected persons' landmarks from classification, form scoring, and rep counting.  
*Rationale: Multi-person tracking would create ambiguous rep counts and calorie totals; a single deterministic "nearest person" rule keeps the system predictable for home/shared-space use without requiring identity recognition (which would conflict with the privacy-first principle).*

---

## 2. Exercise Classification

**REQ-2.1**  
WHEN landmark data is available for a frame, THE SYSTEM SHALL classify the current exercise from the set of supported types: squat, push-up, lunge, bicep curl, shoulder press, and plank.

**REQ-2.2**  
WHEN the classifier's confidence for the top-predicted exercise type is below 0.6, THE SYSTEM SHALL treat the exercise as unrecognized and not update the active exercise label for that frame.  
*Rationale: Premature exercise switching based on low-confidence frames corrupts rep counts and calorie totals.*

**REQ-2.3**  
WHEN the exercise has been unrecognized for more than 3 consecutive seconds, THE SYSTEM SHALL display an "Exercise not recognized — adjust position" message to the user.

**REQ-2.4**  
WHEN the classified exercise type changes from the previously confirmed exercise type with confidence ≥ 0.6 sustained for at least 10 consecutive frames, THE SYSTEM SHALL update the active exercise label, close the current set, and begin a new set under the new exercise type.  
*Rationale: Requiring sustained confidence prevents spurious exercise switches mid-rep.*

**REQ-2.5**  
WHILE a session is active, THE SYSTEM SHALL maintain the last confirmed exercise type as the active type until a new type is confirmed or the session ends.

---

## 3. Posture / Form Correction

**REQ-3.1**  
WHILE a session is active and an exercise type is confirmed, THE SYSTEM SHALL evaluate joint angles relevant to that exercise on every processed frame.

**REQ-3.2**  
WHEN a joint angle deviates from the acceptable range defined for the active exercise, THE SYSTEM SHALL generate a specific corrective cue (e.g., "Drive knees out", "Keep chest up") rather than a generic warning.  
*Rationale: Exercise-specific cues are actionable; generic "bad form" alerts do not guide correction.*

**REQ-3.3**  
WHEN multiple joint angle violations are detected in the same frame, THE SYSTEM SHALL prioritize and surface no more than 2 corrective cues at a time, ordered by severity.  
*Rationale: Displaying too many simultaneous cues overwhelms the user during an active rep.*

**REQ-3.4**  
WHEN the user's form is within all acceptable joint angle ranges for the active exercise, THE SYSTEM SHALL display a positive form indicator and assign a form score of 100 for that frame.

**REQ-3.5**  
WHILE a session is active, THE SYSTEM SHALL compute a rolling form score (0–100) per frame based on the proportion and magnitude of joint angle violations, and maintain a per-set average form score.

**REQ-3.6**  
WHEN the user is partially out of frame such that required landmarks are low-confidence (per REQ-1.3), THE SYSTEM SHALL suspend corrective cue generation and display only the "Move into frame" warning, not a form violation cue.  
*Rationale: Issuing form corrections based on occluded landmarks produces incorrect and confusing feedback.*

**REQ-3.7**  
WHEN a plank is the active exercise, THE SYSTEM SHALL evaluate form on a time basis (hold duration and alignment) rather than rep-cycle basis, and generate cues specific to static hold exercises (e.g., "Drop hips slightly", "Engage core").

---

## 4. Rep Counting

**REQ-4.1**  
WHILE a session is active and an exercise type is confirmed, THE SYSTEM SHALL count a completed rep when the relevant joint angle sequence for that exercise completes one full concentric–eccentric cycle within defined angle thresholds.

**REQ-4.2**  
WHEN a joint angle cycle does not reach the minimum range of motion threshold for the active exercise, THE SYSTEM SHALL not count it as a completed rep.  
*Rationale: Partial reps should not inflate rep counts or calorie estimates.*

**REQ-4.3**  
WHEN a rep is counted, THE SYSTEM SHALL increment the rep counter for the current set and display the updated count to the user immediately.

**REQ-4.4**  
WHEN the user pauses movement for more than 8 seconds after completing at least one rep, THE SYSTEM SHALL automatically close the current set, record it with its rep count and average form score, and prepare a new set.

**REQ-4.5**  
WHEN the exercise type changes (per REQ-2.4), THE SYSTEM SHALL close the current set before opening a new set under the new exercise type, preserving the rep count of the closed set.

**REQ-4.6**  
WHILE a session is active, THE SYSTEM SHALL track the total rep count across all sets and the per-set rep counts independently.

**REQ-4.7**  
WHEN a plank is the active exercise, THE SYSTEM SHALL track hold duration in seconds rather than rep count.

---

## 5. Calorie Estimation

**REQ-5.1**  
WHILE a session is active with a confirmed exercise type and a known user weight, THE SYSTEM SHALL continuously estimate calories burned using the formula: `Calories = MET × weight_kg × duration_hours`, where MET is the value assigned to the confirmed exercise type.

**REQ-5.2**  
WHEN the user has not set their weight in their profile before starting a session, THE SYSTEM SHALL block session start and prompt the user to enter their weight.  
*Rationale: Without user weight, the MET equation cannot produce a valid calorie estimate.*

**REQ-5.3**  
WHEN the active exercise type changes mid-session (per REQ-2.4), THE SYSTEM SHALL freeze the calorie total accumulated under the previous exercise type and begin accumulating calories using the MET value for the new exercise type from the point of change.

**REQ-5.4**  
WHEN a session ends, THE SYSTEM SHALL record the total calories burned as the sum of all per-exercise-type calorie segments accumulated during the session.

**REQ-5.5**  
WHILE a session is active, THE SYSTEM SHALL display the running calorie estimate to the user, updated at least once every 5 seconds.

**REQ-5.6**  
WHEN the user updates their weight in their profile between sessions, THE SYSTEM SHALL use the updated weight for all future sessions but SHALL NOT retroactively recalculate calories for completed sessions.

---

## 6. Session Management

**REQ-6.1**  
WHEN the user initiates a session start action and their weight is set, THE SYSTEM SHALL create a new session record, begin the CV pipeline, and transition the UI to the active session view.

**REQ-6.2**  
WHEN the user initiates a session end action, THE SYSTEM SHALL stop the CV pipeline, finalize all calorie and rep calculations, persist the complete session record to the local database, and transition the UI to the session summary view.

**REQ-6.3**  
WHEN the user's browser tab is closed or the network connection to the local server is interrupted while a session is active, THE SYSTEM SHALL persist a partial session record to the database with all data accumulated up to the point of interruption, marked with a status of "interrupted".

**REQ-6.4**  
WHEN the user returns to the app after an interrupted session, THE SYSTEM SHALL display a notification that the previous session was interrupted and show the partial data in session history.

**REQ-6.5**  
WHEN a session is active, THE SYSTEM SHALL prevent starting a second concurrent session.  
*Rationale: The system supports only one active session per server instance per the steering document.*

**REQ-6.6**  
WHILE a session is active, THE SYSTEM SHALL continuously persist incremental session state (rep counts, calorie total, form scores) to the database at intervals of no more than 30 seconds, so that interruptions lose at most 30 seconds of data.

---

## 7. History & Progress Tracking

**REQ-7.1**  
WHEN the user navigates to the session history view, THE SYSTEM SHALL retrieve and display all completed and interrupted sessions stored in the local database, ordered by most recent first.

**REQ-7.2**  
WHEN the user selects a past session, THE SYSTEM SHALL display the session's exercise type, total reps, sets, calories burned, duration, average form score, and per-set form score trend.

**REQ-7.3**  
WHEN the user views their progress dashboard, THE SYSTEM SHALL display a time-series chart of calories burned per session over the most recent 30 sessions.

**REQ-7.4**  
WHEN the user views their progress dashboard, THE SYSTEM SHALL display the average form score trend across the most recent 10 sessions for each exercise type that has at least 2 recorded sessions.

**REQ-7.5**  
WHILE the user has at least one completed session on each of N consecutive calendar days, THE SYSTEM SHALL record and display a streak of N days.

**REQ-7.6**  
WHEN the user's streak is broken (no completed session on a calendar day), THE SYSTEM SHALL reset the streak counter to 0 and retain the user's historical best streak for display.

**REQ-7.7**  
WHEN the user sets a daily or weekly calorie goal, THE SYSTEM SHALL track progress toward that goal based on completed session calorie totals and display the current progress.

**REQ-7.8**  
WHEN a daily calorie goal is met, THE SYSTEM SHALL display a goal-achieved notification for that day.

---

## 8. Local Network Access

**REQ-8.1**  
WHEN the backend server is started, THE SYSTEM SHALL bind to `0.0.0.0` on the configured port, making the application accessible to any device on the same local network via the host machine's local IP address.

**REQ-8.2**  
WHEN a mobile browser on the same Wi-Fi network accesses the application via the host's local IP, THE SYSTEM SHALL serve a fully functional, responsive interface including camera access, real-time feedback, and session management.

**REQ-8.3**  
WHEN a browser that does not support `getUserMedia` or WebSocket connections attempts to access the application, THE SYSTEM SHALL display a compatibility warning listing the requirement and recommend a supported browser.

**REQ-8.4**  
WHEN the application is loaded in any browser, THE SYSTEM SHALL not make any requests to external domains, third-party CDNs, analytics services, or any IP address outside the local network.  
*Rationale: Any external request would violate the privacy-first principle even if no personal data is transmitted.*

**REQ-8.5**  
IF a runtime dependency unexpectedly attempts to initiate a network request to an external address, THEN THE SYSTEM SHALL log the attempt as a privacy violation error and block the request at the application layer.

---

## 9. User Profile

**REQ-9.1**  
WHEN a user opens the application for the first time (no profile exists), THE SYSTEM SHALL display a profile setup screen requiring the user to enter their weight in kilograms before any session can be started.

**REQ-9.2**  
WHEN the user submits a weight value that is not a positive number between 20 kg and 300 kg, THE SYSTEM SHALL reject the input and display a validation error.

**REQ-9.3**  
WHEN the user updates their name in their profile, THE SYSTEM SHALL save the change immediately and reflect it throughout the application without requiring a session restart.

**REQ-9.4**  
WHEN the user attempts to update their weight while a session is active, THE SYSTEM SHALL reject the update, display a message indicating that weight cannot be changed during an active session, and preserve the weight used at session start for that session's calorie calculations.  
*Rationale: Changing weight mid-session would make the calorie total internally inconsistent.*

**REQ-9.5**  
WHEN the user updates their weight between sessions, THE SYSTEM SHALL store the new weight and use it for all subsequent sessions.

**REQ-9.6**  
WHILE a user profile exists with a valid weight, THE SYSTEM SHALL not prompt the user for weight again on subsequent app loads unless the weight has been cleared.

---

## 10. Offline Operation

**REQ-10.1**  
WHEN the host machine has no internet connection, THE SYSTEM SHALL start and operate with full functionality including pose detection, exercise classification, form correction, rep counting, calorie estimation, session management, and history retrieval.

**REQ-10.2**  
WHILE the application is running, THE SYSTEM SHALL serve all frontend assets (HTML, CSS, JavaScript, fonts, icons) from the local backend server, with no dependency on external CDNs or remote asset hosts.  
*Rationale: Runtime CDN dependency would break the app during offline use.*

**REQ-10.3**  
WHEN the application initializes, THE SYSTEM SHALL load all ML models and CV dependencies from the local filesystem without making any network requests.

**REQ-10.4**  
IF any application component attempts to load a resource from an external URL at runtime, THEN THE SYSTEM SHALL treat this as a configuration error, log it, and surface a startup warning to the developer/operator.

**REQ-10.5**  
WHEN running fully offline, THE SYSTEM SHALL produce calorie estimates, form scores, and rep counts with the same accuracy as when an internet connection is present, as no online components contribute to these calculations.

---

*End of requirements. Design decisions (data models, API schemas, module architecture) are specified in `design.md`.*
