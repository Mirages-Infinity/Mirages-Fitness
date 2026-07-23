# 🚀 Publicar FitTrack en PythonAnywhere

Guía paso a paso. Al final tu app estará en `https://TUUSUARIO.pythonanywhere.com`,
con HTTPS (requisito de la PWA y del webhook de Mercado Pago).

> Donde diga `TUUSUARIO`, reemplaza por tu nombre de usuario de PythonAnywhere.

---

## Paso 1 — Crear la cuenta

1. Entra a **https://www.pythonanywhere.com** → *Pricing & signup* → **Create a Beginner account** (gratis).
2. Elige bien tu nombre de usuario: tu app vivirá en `TUUSUARIO.pythonanywhere.com`.

> El plan gratis sirve para arrancar. Limitaciones: la web "duerme" si no la visitas
> en 3 meses (te llega un email para renovarla con 1 clic) y el acceso a APIs externas
> está limitado a una lista blanca (Mercado Pago **sí está incluido**).
> El plan Hacker (US$5/mes) quita esas limitaciones.

## Paso 2 — Subir el código

**Opción A (simple): archivo ZIP**

1. En tu PC, comprime la carpeta del proyecto **sin** `venv/`, `staticfiles/` ni `db.sqlite3`
   (incluye: `config/`, `core/`, `static/`, `manage.py`, `requirements.txt`).
2. En PythonAnywhere: pestaña **Files** → **Upload a file** → sube el zip.
3. Abre una **Bash console** (pestaña Consoles) y descomprime:
   ```bash
   unzip TRAINING-PERSONAL.zip -d ~/fittrack
   cd ~/fittrack
   ls   # debes ver manage.py
   ```

**Opción B (mejor para actualizar despues): GitHub**

Si subes el proyecto a un repositorio de GitHub, en la consola Bash de PythonAnywhere:
```bash
git clone https://github.com/TUUSUARIO-GITHUB/fittrack.git ~/fittrack
```
Y cada actualización futura será solo `cd ~/fittrack && git pull`.

## Paso 3 — Crear el entorno virtual e instalar dependencias

En la **Bash console** de PythonAnywhere:

```bash
mkvirtualenv fittrack-env --python=python3.13
pip install -r ~/fittrack/requirements.txt
```

> ⚠️ Django 6 necesita Python 3.12 o superior. Si `python3.13` no existe en tu cuenta,
> prueba `--python=python3.12`. Si tampoco, avísame y adaptamos el proyecto.

## Paso 4 — Crear la base de datos y el admin

En la misma consola:

```bash
cd ~/fittrack
python manage.py migrate
python manage.py seed
python manage.py createsuperuser   # crea TU cuenta de administrador
python manage.py collectstatic --noinput
```

## Paso 5 — Configurar la web app

1. Pestaña **Web** → **Add a new web app** → *Next* →
   **Manual configuration** (¡NO elijas "Django"!) → **Python 3.13** (o la que usaste).
2. En la sección **Virtualenv** escribe: `fittrack-env`
3. En la sección **Code**: *Source code* = `/home/TUUSUARIO/fittrack`
4. Clic en el enlace del **WSGI configuration file** y reemplaza TODO su contenido por:

```python
import os
import sys

path = '/home/TUUSUARIO/fittrack'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DJANGO_DEBUG'] = 'False'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'TUUSUARIO.pythonanywhere.com'
os.environ['DJANGO_SECRET_KEY'] = 'PEGA-AQUI-UNA-CLAVE-LARGA-Y-ALEATORIA'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

> Para generar la clave secreta, en la consola Bash:
> ```bash
> python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

5. En la sección **Static files** de la pestaña Web, agrega DOS entradas:

   | URL        | Directory                              |
   |------------|----------------------------------------|
   | `/static/` | `/home/TUUSUARIO/fittrack/staticfiles` |
   | `/media/`  | `/home/TUUSUARIO/fittrack/media`       |

6. Botón verde **Reload** (arriba de la pestaña Web).

## Paso 6 — ¡Probar! 🎉

- Abre `https://TUUSUARIO.pythonanywhere.com` desde tu celular.
- Inicia sesión, y desde Chrome: menú ⋮ → **"Agregar a pantalla principal"** → la PWA
  queda instalada como app.
- Configura Mercado Pago en **Panel → Suscripción y pagos** con tus credenciales
  reales (`APP_USR-...`). El webhook ya funcionará porque hay HTTPS.

## Paso 7 — Instalarla como app en los celulares 📲

Una vez que la web esté funcionando en `https://TUUSUARIO.pythonanywhere.com`:

**Android (Chrome):**
1. Abre la URL en Chrome.
2. Chrome mostrará el aviso **"Agregar FitTrack a la pantalla principal"**
   (o menú ⋮ → **"Instalar aplicación"** / **"Agregar a pantalla principal"**).
3. Confirma → aparece el ícono 🏋️ en el escritorio del teléfono. Se abre a pantalla
   completa, sin barra del navegador, como cualquier app.

**iPhone (Safari — debe ser Safari, no Chrome):**
1. Abre la URL en Safari.
2. Toca el botón **Compartir** (cuadrado con flecha hacia arriba).
3. Baja y toca **"Añadir a pantalla de inicio"** → **Añadir**.
4. Aparece el ícono en el escritorio y se abre a pantalla completa.

> Esto es lo que les enseñas a tus clientes: entrar a la URL una vez e instalarla.
> No hay Play Store ni App Store de por medio.

## Actualizaciones automáticas desde GitHub 🔄

El proyecto incluye un webhook de auto-deploy: cada `git push` a GitHub actualiza
PythonAnywhere solo. Para activarlo:

1. **Clona con GitHub en PythonAnywhere** (Paso 2, opción B), no con ZIP.
2. **Inventa un secreto** (una frase larga aleatoria) y agrégalo al archivo WSGI,
   junto a las otras variables:
   ```python
   os.environ['GITHUB_WEBHOOK_SECRET'] = 'tu-frase-secreta-larga'
   os.environ['PA_WSGI_FILE'] = '/var/www/TUUSUARIO_pythonanywhere_com_wsgi.py'
   ```
   (la ruta exacta del WSGI aparece en la pestaña Web, sección Code).
3. **En GitHub**: tu repositorio → **Settings → Webhooks → Add webhook**:
   - *Payload URL*: `https://TUUSUARIO.pythonanywhere.com/webhook/github/`
   - *Content type*: `application/json`
   - *Secret*: la misma frase secreta del paso 2
   - *Events*: **Just the push event** → **Add webhook**
4. Presiona **Reload** en PythonAnywhere una vez (para cargar las variables nuevas).

Desde ahora, cada vez que hagas push:
```
git push  →  GitHub avisa a tu app  →  git pull + migrate + collectstatic + reload
```
En GitHub (Settings → Webhooks → Recent Deliveries) puedes ver la respuesta de cada
deploy con el detalle de lo que se ejecutó.

**Actualización manual** (si no configuras el webhook): en una consola Bash de
PythonAnywhere:

```bash
cd ~/fittrack
git pull
workon fittrack-env
python manage.py migrate
python manage.py collectstatic --noinput
```

y presiona **Reload** en la pestaña Web.

## Problemas comunes

| Síntoma | Solución |
|---|---|
| Error 400 al abrir la web | Revisa `DJANGO_ALLOWED_HOSTS` en el WSGI (debe ser exactamente tu dominio) |
| La web se ve sin estilos | Falta el mapeo `/static/` o no corriste `collectstatic` |
| Las imágenes de ejercicios no cargan | Falta el mapeo `/media/` |
| Error al pagar con MP | Verifica el Access Token en Panel → Suscripción y pagos |
| Cambios que no aparecen | Olvidaste presionar **Reload** en la pestaña Web |
