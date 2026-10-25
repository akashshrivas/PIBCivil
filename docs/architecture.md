# UPSCByte — System Architecture (PIBCivil: Current Affairs feature)

## 1. Project Overview

UPSCByte is a broader UPSC preparation platform. PIBCivil, its current-affairs feature, is a data-driven platform that collects official
Government of India information, processes it into structured data, enriches
it for UPSC preparation, and exposes it through a web application.

The initial data source is the Press Information Bureau (PIB).

The system is designed so that additional sources such as PRS, RBI,
Economic Survey, and other official government sources can be added later.

---

# 2. Core Objective

Convert raw government information into structured, searchable and
UPSC-relevant knowledge.

```text
Government Sources
        ↓
     Extract
        ↓
      Parse
        ↓
      Clean
        ↓
    Transform
        ↓
   Deduplicate
        ↓
     Store
        ↓
    Classify
        ↓
  UPSC Enrichment
        ↓
     Backend
        ↓
       UI


# 3. High-Level Architecture
                         DATA SOURCES
                              │
                ┌─────────────┼─────────────┐
                │             │             │
               PIB           PRS           RBI
                │             │             │
                └─────────────┼─────────────┘
                              │
                              ▼
                       DATA INGESTION
                              │
                              ▼
                         EXTRACTION
                              │
                              ▼
                            PARSE
                              │
                              ▼
                           CLEAN
                              │
                              ▼
                         TRANSFORM
                              │
                              ▼
                        DEDUPLICATE
                              │
                              ▼
                         DATA STORE
                              │
                              ▼
                    UPSC INTELLIGENCE
                              │
                ┌─────────────┼─────────────┐
                │             │             │
             GS Mapping   Prelims/Mains   Tags
                │             │             │
                └─────────────┼─────────────┘
                              │
                              ▼
                           FASTAPI
                              │
                              ▼
                         NEXT.JS UI
                              │
                ┌─────────────┼─────────────┐
                │             │             │
             Articles      Search       Compilations