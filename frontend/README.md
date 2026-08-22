# Planificador Académico UMSS — Astro + React

Frontend estático para explorar la malla curricular, revisar progreso y armar horarios. Todo el trabajo personalizado ocurre en el navegador: el Kardex se procesa con PDF.js y se guarda en `localStorage`; ningún PDF ni dato personal se envía al Worker.

## Desarrollo y verificación

Desde `frontend/`:

```sh
npm install
npm run dev
npm run test
npm run check
npm run build
npm run preview
```

El build estático se genera en `frontend/dist/`.

## Deploy temporal en Cloudflare Workers

El Worker usa Assets estáticos y el nombre temporal `planificador-academico-umss-temp`.

```sh
npx wrangler login
npm run deploy:dry
npm run deploy
```

`wrangler login` abre el navegador para autorizar la cuenta de Cloudflare. El deploy devuelve una URL `https://planificador-academico-umss-temp.<subdominio>.workers.dev` para las pruebas.

Para publicar con tu dominio:

1. Ejecuta `npx wrangler login` con la cuenta que administra el dominio.
2. Cambia `name` en `wrangler.jsonc` al nombre definitivo del Worker.
3. En Cloudflare, abre **Workers & Pages → tu Worker → Settings → Domains & Routes → Add Custom Domain** y selecciona el dominio/subdominio.
4. También puedes declarar `routes` en `wrangler.jsonc` si necesitas una ruta administrada por zona; el DNS y el dominio deben estar en la misma cuenta.
5. Verifica `/`, `/malla`, `/progreso`, `/horario` y `/calendario-academico` después del deploy.

El sitio no requiere KV, D1, R2, Durable Objects ni endpoints. La información de Kardex permanece local en cada navegador; limpiar los datos del sitio elimina ese historial.

## Rutas

- `/` y `/malla`: malla curricular, relaciones, menciones y técnicos.
- `/progreso` y `/nuevo`: progreso y carga/registro de Kardex.
- `/horario` y `/horario/calendario`: planificador y calendario.
- `/guia`: instrucciones de uso.
- `/calendario-academico`: visor/fallback del calendario institucional.
