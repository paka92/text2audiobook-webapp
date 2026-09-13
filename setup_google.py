"""Save a Cloud TTS API key locally without echoing it or sending requests."""
import getpass
import os
from pathlib import Path


def main():
    key = getpass.getpass('Google Cloud Text-to-Speech API anahtarını yapıştırıp Enter basın (görünmez): ').strip()
    if not key or any(char.isspace() for char in key):
        raise SystemExit('Geçerli, boşluksuz bir anahtar girin. Kayıt değiştirilmedi.')
    state = Path(__file__).resolve().parent / '.state'
    state.mkdir(exist_ok=True)
    path = state / 'google-api-key.txt'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(key)
    print('Anahtar yerel olarak kaydedildi. Arayüzde Google seslerini getir düğmesine basın.')


if __name__ == '__main__':
    main()
