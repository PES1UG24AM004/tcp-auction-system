import sys
import os
import datetime

CERT_FILE = "server.crt"
KEY_FILE  = "server.key"

def main():
    force = "--force" in sys.argv
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE) and not force:
        print(f"Certificate files already exist: {CERT_FILE}, {KEY_FILE}")
        print("Use --force to regenerate.")
        return
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509 import IPAddress
        import ipaddress
    except ImportError:
        print("ERROR: 'cryptography' package required.\n  Install with:  pip install cryptography")
        sys.exit(1)
    print("Generating 2048-bit RSA key pair…")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.datetime.now(datetime.timezone.utc)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "AuctionServer"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AuctionApp"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"), IPAddress(ipaddress.IPv4Address("127.0.0.1"))]), critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(KEY_FILE, "wb") as f: f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    with open(CERT_FILE, "wb") as f: f.write(cert.public_bytes(serialization.Encoding.PEM))
    print(f"✅  Certificate: {CERT_FILE}\n✅  Private key: {KEY_FILE}")
    print(f"   Valid for 10 years (until {now + datetime.timedelta(days=3650):%Y-%m-%d})\n   SANs: localhost, 127.0.0.1")

if __name__ == "__main__":
    main()