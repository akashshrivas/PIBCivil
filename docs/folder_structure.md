pibmania/
│
├── README.md
├── .env
├── .gitignore
├── docker-compose.yml
├── pyproject.toml
│
├── data/
│   ├── raw/                    # Raw PIB responses
│   ├── processed/              # Cleaned/normalized data
│   └── exports/                # Generated JSON/PDFs
│
├── backend/
│   │
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   │
│   │   ├── api/                # REST API
│   │   │   ├── articles.py
│   │   │   ├── categories.py
│   │   │   ├── ministries.py
│   │   │   ├── search.py
│   │   │   └── compilations.py
│   │   │
│   │   ├── core/               # Application configuration
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   │
│   │   ├── models/             # Database models
│   │   │   ├── article.py
│   │   │   ├── ministry.py
│   │   │   ├── category.py
│   │   │   └── tag.py
│   │   │
│   │   ├── schemas/             # API/Pydantic schemas
│   │   │   ├── article.py
│   │   │   ├── category.py
│   │   │   └── compilation.py
│   │   │
│   │   ├── services/            # Business logic
│   │   │   ├── article_service.py
│   │   │   ├── search_service.py
│   │   │   └── compilation_service.py
│   │   │
│   │   └── db/
│   │       ├── database.py
│   │       └── repositories/
│   │           └── article_repository.py
│   │
│   └── tests/
│
├── pipeline/
│   │
│   ├── extract/                 # ① GET DATA
│   │   ├── rss_fetcher.py
│   │   └── article_fetcher.py
│   │
│   ├── parse/                   # ② UNDERSTAND SOURCE
│   │   ├── rss_parser.py
│   │   └── pib_parser.py
│   │
│   ├── clean/                   # ③ CLEAN DATA
│   │   ├── text_cleaner.py
│   │   ├── html_cleaner.py
│   │   └── date_cleaner.py
│   │
│   ├── transform/               # ④ STANDARDIZE
│   │   ├── normalizer.py
│   │   ├── ministry_mapper.py
│   │   └── schema_mapper.py
│   │
│   ├── dedup/                   # ⑤ REMOVE DUPLICATES
│   │   ├── hash_dedup.py
│   │   └── dedup_engine.py
│   │
│   ├── classify/                # ⑥ UPSC INTELLIGENCE
│   │   ├── subject_classifier.py
│   │   ├── relevance_classifier.py
│   │   ├── syllabus_mapper.py
│   │   └── tagger.py
│   │
│   ├── storage/                 # ⑦ PERSIST DATA
│   │   ├── json_writer.py
│   │   ├── database_writer.py
│   │   └── storage_manager.py
│   │
│   └── pipeline.py              # Runs complete pipeline
│
├── frontend/
│   │
│   ├── app/
│   │   ├── page.tsx             # Landing page
│   │   │
│   │   ├── articles/
│   │   │   ├── page.tsx
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   │
│   │   ├── subjects/
│   │   │   └── [subject]/
│   │   │       └── page.tsx
│   │   │
│   │   ├── compilations/
│   │   │   └── page.tsx
│   │   │
│   │   └── search/
│   │       └── page.tsx
│   │
│   ├── components/
│   │   ├── article/
│   │   ├── navigation/
│   │   ├── search/
│   │   ├── filters/
│   │   └── ui/
│   │
│   ├── lib/
│   │   └── api.ts
│   │
│   └── public/
│
├── scripts/
│   ├── run_pipeline.py
│   ├── ingest_pib.py
│   └── generate_pdf.py
│
├── database/
│   ├── migrations/
│   └── schema.sql
│
└── docs/
    ├── architecture.md
    ├── data-model.md
    └── api.md