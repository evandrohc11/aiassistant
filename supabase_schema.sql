-- =====================================================================
-- Personal Agent — Supabase schema (redesign of my_db.db)
-- Run this in the Supabase SQL editor BEFORE importing.
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

create table if not exists projects (
  id        uuid primary key default gen_random_uuid(),
  owner_id  uuid references auth.users default auth.uid(),
  name      text not null,
  unique (owner_id, name)
);

-- ---------- core ledger ----------
create table if not exists transactions (
  id            uuid primary key default gen_random_uuid(),
  owner_id      uuid references auth.users default auth.uid(),
  legacy_code   integer,
  occurred_on   date,
  amount        numeric(14,2) not null,
  currency      text not null default 'CAD',
  direction     text check (direction in ('income','expense')),
  category_id   uuid references categories,
  label         text,
  merchant      text,
  project_id    uuid references projects,
  account_id    uuid references accounts,
  account_raw   text,
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

-- ---------- mood journal ----------
create table if not exists feelings_taxonomy (
  id        uuid primary key default gen_random_uuid(),
  feeling   text,
  sensation text,
  emotion   text
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

-- ---------- tasks ----------
create table if not exists tasks (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid references auth.users default auth.uid(),
  title       text not null,
  status      text not null default 'open' check (status in ('open','done','cancelled')),
  due_date    date,
  notes       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz
);
create index if not exists ix_tasks_owner_due on tasks (owner_id, due_date, status);

-- ---------- agent memory + learned rules ----------
create table if not exists agent_memory (
  id           uuid primary key default gen_random_uuid(),
  owner_id     uuid references auth.users default auth.uid(),
  kind         text not null check (kind in ('rule','decision','preference','fact')),
  topic_key    text not null,
  value        text not null,
  status       text not null default 'settled' check (status in ('settled','superseded')),
  source       text,
  decided_at   timestamptz not null default now(),
  last_updated timestamptz not null default now()
);
create index if not exists ix_mem_topic on agent_memory (owner_id, topic_key, status);

create table if not exists category_rules (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid references auth.users default auth.uid(),
  match_type  text not null check (match_type in ('merchant','keyword')),
  pattern     text not null,
  category_id uuid references categories,
  created_at  timestamptz not null default now(),
  unique (owner_id, match_type, pattern)
);

-- Cross-user shared rules: any authenticated user can read; insert/update only
-- when the pattern is genuinely generic (no PII — merchant names only).
-- The agent checks personal rules first, then falls back to shared rules.
create table if not exists shared_category_rules (
  id           uuid primary key default gen_random_uuid(),
  match_type   text not null check (match_type in ('merchant','keyword')),
  pattern      text not null,           -- lowercase normalised, e.g. 'uber'
  category_name text not null,          -- canonical name, not a FK (cross-user)
  confidence   integer not null default 1,  -- incremented each time a user confirms it
  created_at   timestamptz not null default now(),
  unique (match_type, pattern)
);
-- Anyone authenticated can read; any authenticated user can upsert (increment confidence)
create policy shared_rules_read  on shared_category_rules for select to authenticated using (true);
create policy shared_rules_write on shared_category_rules for insert to authenticated with check (true);
create policy shared_rules_update on shared_category_rules for update to authenticated using (true);

-- ---------- Row Level Security ----------
alter table accounts          enable row level security;
alter table categories        enable row level security;
alter table projects          enable row level security;
alter table tasks             enable row level security;
alter table transactions      enable row level security;
alter table mood_entries      enable row level security;
alter table agent_memory      enable row level security;
alter table category_rules    enable row level security;
alter table shared_category_rules enable row level security;

do $$
declare t text;
begin
  foreach t in array array['accounts','categories','projects','tasks','transactions',
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
