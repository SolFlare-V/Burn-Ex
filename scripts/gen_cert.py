"""
Generate a self-signed TLS certificate and private key for local HTTPS development.

Outputs:
  certs/local.crt  -- self-signed certificate (valid 825 days)
  certs/local.key  -- RSA private key

The certificate includes:
  - CN=localhost
  - SAN: DNS:localhost, IP:127.0.0.1, IP:0.0.0.0
  - Plus all local-network IPs detected at generation time

Usage:
  python scripts/gen_cert.py
"""
import ipaddress
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_DIR = Path(__file__).parent.parent / "certs"
CERT_DIR.mkdir(exist_ok=True)

CERT_PATH = CERT_DIR / "local.crt"
KEY_PATH  = CERT_DIR / "local.key"

# Detect local IPs
def get_local_ips():
    ips = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            addr = info[4][0]
            try:
                ip = ipaddress.ip_address(addr)
                if not ip.is_loopback:
                    ips.add(ip)
            except ValueError:
                pass
    except Exception:
        pass
    return ips

local_ips = get_local_ips()

# Generate RSA key
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# Build Subject Alternative Names
san_list = [
    x509.DNSName("localhost"),
    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    x509.IPAddress(ipaddress.IPv4Address("0.0.0.0")),
]
for ip in local_ips:
    san_list.append(x509.IPAddress(ip))
    print(f"  Adding SAN: IP:{ip}")

# Build certificate
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Burn-Ex Local Dev"),
    x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
])

now = datetime.now(timezone.utc)
cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now)
    .not_valid_after(now + timedelta(days=825))
    .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    .sign(key, hashes.SHA256())
)

# Write key
KEY_PATH.write_bytes(
    key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
)

# Write cert
CERT_PATH.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

print(f"\nGenerated:")
print(f"  cert: {CERT_PATH}")
print(f"  key:  {KEY_PATH}")
print(f"\nSANs: localhost, 127.0.0.1, 0.0.0.0" + (f", {', '.join(str(ip) for ip in local_ips)}" if local_ips else ""))
print("\nDone. Accept the browser security warning on first access (expected for self-signed cert).")
