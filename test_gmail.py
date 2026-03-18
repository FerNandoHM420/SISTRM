import smtplib

# Tus datos (ACTUALIZA con la NUEVA contraseña)
EMAIL = 'miguefernandohuanca@gmail.com'
PASSWORD = 'jevxxzitiqxuofox'

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(EMAIL, PASSWORD)
    print("✅ LOGIN EXITOSO")
    server.quit()
except Exception as e:
    print(f"❌ ERROR: {e}")
