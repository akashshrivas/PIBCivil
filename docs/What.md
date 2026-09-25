
## What do folders doing?

                 PIB
                  │
                  ▼
            ┌───────────┐
            │  PIPELINE │  ← Process data
            └─────┬─────┘
                  │
                  ▼
            ┌───────────┐
            │   DATA    │  ← Files / temporary data
            └─────┬─────┘
                  │
                  ▼
            ┌───────────┐
            │ DATABASE  │  ← Persistent storage
            └─────┬─────┘
                  │
                  ▼
            ┌───────────┐
            │ BACKEND   │  ← API / business logic
            └─────┬─────┘
                  │
                  ▼
            ┌───────────┐
            │ FRONTEND  │  ← What users see
            └───────────┘

        SCRIPTS → Run automated tasks
        DOCS    → Explain the system