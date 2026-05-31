-- =====================================================================
-- Personal Agent — Supabase schema (redesign of my_db.db)
-- Run this in the Supabase SQL editor BEFORE importing.
-- Fixes from the legacy SQLite design:
--   * one real DATE instead of separate day/month/year integers
--   * NUMERIC money (no comma-decimal text), explicit currency
--   * dimensions normalized into accounts / categories / projects
--   * messy free-text (bank junk) preserved in *_raw, not lost
--   * a memory layer so the agent stops re-deciding settled things
-- =====================================================================

-- ---------- reference / dimension tables ----------
create table if not exists accounts (
  id        uuid primary key default gen_random_uuid(),
  owner_id  uuid references auth.users default auth.uid(),
  name      text not null,
  kind      text check (kind in ('checking','savings','card','cash','other')),
  currency  text not null default 'CAD',
  unique (owner_id, name)
);

create table if not exists categories (
  id        uuid primary key default gen_random_uuid(),
  owner_id  uuid references auth.users default auth.uid(),
  name      text not null,
  kind      text check (kind in ('income','expense','transfer')),
  unique (owner_id, name)
);

create table if not exists projects (   -- the legacy "operation" context tags
  id        uuid primary key default gen_random_uuid(),
  owner_id  uuid references auth.users default auth.uid(),
  name      text not null,
  unique (owner_id, name)
);

-- ---------- core ledger (replaces tb_event) ----------
create table if not exists transactions (
  id            uuid primary key default gen_random_uuid(),
  owner_id      uuid references auth.users default auth.uid(),
  legacy_code   integer,                 -- tb_event.code, kept for dedupe/traceability
  occurred_on   date,
  amount        numeric(14,2) not null,  -- signed: negative = expense, positive = income
  currency      text not null default 'CAD',
  direction     text check (direction in ('income','expense')),
  category_id   uuid references categories,
  label         text,                    -- e.g. JANTAR, ALMOÇO
  merchant      text,                    -- legacy "details"
  project_id    uuid references projects,
  account_id    uuid references accounts,
  account_raw   text,                    -- original messy "bank" text, preserved
  card          text,
  bill_cycle    text,
  installments  text,
  cleared       boolean not null default true,
  cleared_on    date,
  raw_text      text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz
);
create index if not exists ix_tx_owner_date on transactions (owner_id, occurred_on);
create index if not exists ix_tx_category   on transactions (category_id);
create index if not exists ix_tx_account    on transactions (account_id);
create index if not exists ix_tx_legacy     on transactions (owner_id, legacy_code);

-- ---------- mood journal (replaces tb_feelings + tb_records) ----------
create table if not exists feelings_taxonomy (  -- reference list
  id        uuid primary key default gen_random_uuid(),
  feeling   text,     -- Sentimento
  sensation text,     -- Sensacao
  emotion   text      -- Emocao (Feliz, Triste, Medo, Raiva, ...)
);

create table if not exists mood_entries (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid references auth.users default auth.uid(),
  occurred_at timestamptz not null default now(),
  feeling     text,
  sensation   text,
  emotion     text,
  notes       text,
  created_at  timestamptz not null default now()
);

-- ---------- MEMORY: durable decisions + learned rules (anti-loop) ----------
-- The agent writes here so it never re-asks or re-debates something settled.
create table if not exists agent_memory (
  id           uuid primary key default gen_random_uuid(),
  owner_id     uuid references auth.users default auth.uid(),
  kind         text not null check (kind in ('rule','decision','preference','fact')),
  topic_key    text not null,            -- normalized subject; repeats match on this
  value        text not null,            -- what was decided / preferred
  status       text not null default 'settled' check (status in ('settled','superseded')),
  source       text,                     -- where it came from (whatsapp msg id, etc.)
  decided_at   timestamptz not null default now(),
  last_updated timestamptz not null default now()
);
create index if not exists ix_mem_topic on agent_memory (owner_id, topic_key, status);

-- Concrete finance memory: learned merchant/keyword -> category mappings,
-- so once you categorize "Uber", the agent stops asking.
create table if not exists category_rules (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid references auth.users default auth.uid(),
  match_type  text not null check (match_type in ('merchant','keyword')),
  pattern     text not null,            -- e.g. 'uber', 'ifood'
  category_id uuid references categories,
  created_at  timestamptz not null default now(),
  unique (owner_id, match_type, pattern)
);

-- ---------- Row Level Security (personal, owner-scoped) ----------
alter table accounts          enable row level security;
alter table categories        enable row level security;
alter table projects          enable row level security;
alter table transactions      enable row level security;
alter table mood_entries      enable row level security;
alter table agent_memory      enable row level security;
alter table category_rules    enable row level security;
-- feelings_taxonomy is shared reference data; leave RLS off or add a read-all policy.

do $$
declare t text;
begin
  foreach t in array array['accounts','categories','projects','transactions',
                           'mood_entries','agent_memory','category_rules']
  loop
    execute format($f$
      create policy %1$I_owner_all on %1$I
        for all to authenticated
        using (owner_id = auth.uid())
        with check (owner_id = auth.uid());
    $f$, t);
  end loop;
end $$;
