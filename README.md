# 🏍 La Banda Motera Bot

Sistema automatizado de generación editorial para La Banda Motera.lat.
Corre cada 6 horas vía GitHub Actions. Cero intervención manual.

---

## Setup

1. API Keys: Anthropic `(console.anthropic.com)` + Exa `(exa.ai)`
2. WordPress Application Password: WP Admin → Usuarios → Perfil → Contraseñas de aplicación
3. GitHub Secrets: Settings → Secrets & variables → Actions

| Secret | Valor |
|--------|-------|
| ANTHROPIC_API_KEY | Tu key de Anthropic |
| EXA_API_KEY | Tu key de Exa |
| WP_URL | https://contramanillar.lat |
| WP_USER | Tu usuario de WP |
| WP_APP_PASS | Contraseña de aplicación de WP |

*Construido con Claude API + Exa + GitHub Actions*
