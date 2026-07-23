# 🏋️ FitTrack — Plataforma de entrenamiento personal

Plataforma web **diseñada exclusivamente para celular** que lleva el registro de tus
entrenamientos: el administrador crea el catálogo de ejercicios (con categoría, imagen
y descripción) y cada usuario arma su rutina diaria/semanal con peso, series y
repeticiones, guardando un historial para ver su progreso con el tiempo.

**Stack:** Python · Django · Tailwind CSS · SQLite · PWA

## 📲 Es una PWA (app instalable)

La plataforma es una **Progressive Web App**: al abrirla desde el celular (con la app
publicada en internet con **HTTPS**), el navegador ofrece **"Agregar a pantalla de
inicio"** y queda instalada con su ícono 🏋️, pantalla completa y sin barra del
navegador — como una app nativa, sin pasar por Play Store ni App Store.

- Android (Chrome): banner de instalación automático, o menú ⋮ → *Agregar a pantalla principal*
- iPhone (Safari): botón Compartir → *Añadir a pantalla de inicio*

> En localhost funciona para probar, pero para instalarla en los teléfonos de tus
> clientes necesitas publicarla en un hosting con HTTPS (el mismo requisito del
> webhook de Mercado Pago).

## Cómo iniciar

```bash
venv\Scripts\python.exe manage.py runserver
```

Abrir en el navegador: http://localhost:8000 (idealmente con la vista móvil del
navegador o desde el celular en la misma red).

## Credenciales iniciales

| Rol   | Usuario | Contraseña  |
|-------|---------|-------------|
| Admin | `admin` | `admin1234` |

> ⚠️ Cambia esta contraseña. Los usuarios normales se registran desde la propia app
> en **/registro/**.

## Roles

### Administrador (pestaña "Panel" en la barra inferior)
- Dashboard con estadísticas (ejercicios, categorías, usuarios, entrenamientos)
- CRUD de **categorías** (Espalda, Pecho, Hombros, Abdomen... con emoji)
- CRUD de **ejercicios** (título, imagen, descripción, categoría)
- Gestión de **usuarios**: activar, desactivar o eliminar cuentas
- Todo desde la página, sin entrar al admin de Django

### Usuario
- Se registra con **RUT chileno válido** (dígito verificador verificado; una sola cuenta por RUT)
- **Hoy**: rutina del día con **check de completado** por ejercicio y **barra de progreso
  diaria**; el botón "Registrar entrenamiento" guarda en el historial los ejercicios marcados
- **Rutina**: organiza la semana (Lunes a Domingo), edita cada ejercicio
- **Ejercicios**: catálogo con búsqueda y filtro por categoría. Dos tipos:
  - *Fuerza*: peso (kg), series y repeticiones
  - *Cardio* (caminar, trotar, correr): minutos y kilómetros
- **Progreso**: historial de sesiones y evolución por ejercicio (kg en fuerza, km en cardio)

El admin además puede **liberar de pago** a usuarios elegidos (Panel → Usuarios → "🎁 Liberar"):
acceso gratis sin límite hasta que se lo quite.

## Suscripción y pagos (Mercado Pago)

La plataforma es de **pago por suscripción mensual**:

1. Al registrarse, cada usuario recibe **días de prueba gratis** (configurable, por defecto 7).
2. Al vencer la prueba (o el mes pagado), la app **se bloquea automáticamente** y solo
   muestra la pantalla de suscripción.
3. El usuario paga con **Mercado Pago** (tarjeta, QR, etc.) y se le acreditan 30 días.
4. El admin también puede activar meses manualmente desde **Panel → Usuarios → "+1 mes"**
   (útil para pagos en efectivo o transferencia).

### Configurar Mercado Pago

1. Crea una cuenta en [mercadopago.com](https://www.mercadopago.com) y entra a
   **Tus integraciones → Crear aplicación**.
2. Copia el **Access Token** y la **Public Key** (usa las credenciales de *prueba*
   `TEST-...` para probar sin dinero real, y las de *producción* `APP_USR-...` para cobrar).
3. En la app: **Panel → Suscripción y pagos** → pega las credenciales, define el
   precio mensual, la moneda y los días de prueba → Guardar.

> **Nota:** el webhook de confirmación (`/webhook/mercadopago/`) requiere que la app
> esté publicada en internet con HTTPS. En localhost, el pago se acredita igualmente
> cuando el usuario vuelve del checkout (URL de retorno). Los admins no pagan.

## Comandos útiles

```bash
venv\Scripts\python.exe manage.py seed
```
Recarga las categorías y ejercicios de ejemplo (no duplica los existentes).

```bash
venv\Scripts\python.exe manage.py createsuperuser
```
Crea otro administrador.

## Estructura

```
config/          Configuración del proyecto Django
core/
  models.py      Category, Exercise, RoutineItem, WorkoutLog,
                 SiteConfig, Subscription, Payment
  views.py       Vistas de usuario + suscripción/pagos + panel de administración
  payments.py    Integración con Mercado Pago (Checkout Pro + webhook)
  middleware.py  Bloqueo automático de suscripciones vencidas
  signals.py     Prueba gratis automática al registrarse
  forms.py       Formularios con estilos Tailwind
  templates/
    base.html    Layout móvil + barra de navegación inferior
    auth/        Login y registro
    user/        Hoy, rutina, catálogo, historial, progreso
    panel/       Dashboard, categorías, ejercicios, usuarios
media/           Imágenes de ejercicios subidas por el admin
```
