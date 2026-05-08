# Ejemplos few-shot para CAG: representan estimaciones historicas que
# se inyectan en cada prompt para estabilizar formato, granularidad y criterio.
ESTIMATION_EXAMPLES = [
    {
        "meeting_summary": (
            "Startup SaaS B2B solicita un modulo de onboarding con autenticacion "
            "email/OAuth, wizard de configuracion inicial, gestion de roles basicos "
            "y dashboard de actividad para administradores."
        ),
        "estimation": """
## Estimacion: Modulo de Onboarding SaaS B2B

### Desglose de tareas (con apoyo de asistentes IA en desarrollo y testing)
1. Discovery funcional y arquitectura tecnica: 10 horas
2. UI/UX (wireframes + componentes base): 18 horas
3. Backend API (usuarios, roles, sesiones): 34 horas
4. Autenticacion (email + OAuth Google + recuperacion password): 20 horas
5. Dashboard inicial de actividad y metricas: 16 horas
6. QA, pruebas E2E y hardening de seguridad basica: 18 horas
7. DevOps ligero (CI, despliegue y observabilidad minima): 8 horas

**Total estimado: 124 horas**
**Tarifa de referencia: 62 EUR/hora (rango 2025 para perfil senior full-stack en Europa)**
**Coste estimado: 7,688 EUR**
**Equipo recomendado: 1 desarrollador/a full-stack senior + 1 QA part-time**
**Duracion estimada: 4-5 semanas**

### Notas
- El uso de asistentes IA reduce entre un 15% y 25% tareas repetitivas de codigo y tests.
- No incluye integraciones enterprise (SSO SAML/OIDC corporativo ni auditoria avanzada).
""".strip(),
    },
    {
        "meeting_summary": (
            "Comercio online en WooCommerce necesita un plugin custom para packs "
            "de productos, reglas de descuento por volumen, compatibilidad con cupones, "
            "sincronizacion de stock y panel de configuracion para marketing."
        ),
        "estimation": """
## Estimacion: Plugin eCommerce para WooCommerce (packs y descuentos)

### Desglose de tareas (plugin development)
1. Analisis funcional y modelado de reglas de negocio: 12 horas
2. Estructura del plugin (arquitectura, hooks y settings): 20 horas
3. Logica de packs, bundles y descuentos por tramos: 38 horas
4. Compatibilidad con cupones, carrito y checkout: 26 horas
5. Sincronizacion de stock y validaciones en catalogo: 18 horas
6. Panel admin del plugin (parametrizacion y mensajes): 16 horas
7. Testing (unitario/integracion), performance y QA en staging: 24 horas
8. Documentacion tecnica y handover: 8 horas

**Total estimado: 162 horas**
**Tarifa de referencia: 58 EUR/hora (promedio 2025 para desarrollo WooCommerce especializado)**
**Coste estimado: 9,396 EUR**
**Equipo recomendado: 1 dev WordPress/WooCommerce senior + 1 QA part-time**
**Duracion estimada: 5-7 semanas**

### Notas
- Con asistentes IA, el ahorro esperado se concentra en scaffolding, refactors y casos de prueba.
- No incluye marketplace multi-vendor, ERP enterprise ni internacionalizacion fiscal completa.
""".strip(),
    },
]
