-- =====================================================================
-- Personal Agent — Supabase schema v2
-- Source data: item.csv, description.csv, cards.csv, audit_log.csv
-- Run this in the Supabase SQL editor BEFORE importing.
-- =====================================================================

-- ---------- credit cards ----------
create table if not exists cards (
  id        integer primary key,          -- legacy id from cards.csv
  owner_id  uuid references auth.users default auth.uid(),
  name      text not null,
  active    boolean not null default true,
  close_day integer                       -- billing cycle close day (1-31)
);

-- ---------- accounts (bank / wallet) ----------
create table if not exists accounts (
  id        uuid primary key default gen_random_uuid(),
  owner_id  uuid references auth.users default auth.uid(),
  name      text not null,
  kind      text check (kind in ('checking','savings','card','cash','other')),
  currency  text not null default 'CAD',
  unique (owner_id, name)
);

-- ---------- categories ----------
create table if not exists categories (
  id        uuid primary key default gen_random_uuid(),
  owner_id  uuid references auth.users default auth.uid(),
  name      text not null,
  kind      text check (kind in ('income','expense','transfer')),
  unique (owner_id, name)
);

-- ---------- labels (item descriptions dimension) ----------
-- Each label maps to a category and carries its routine/active flags.
-- item.description_id → labels.id
create table if not exists labels (
  id          integer primary key,        -- legacy id from description.csv
  owner_id    uuid references auth.users default auth.uid(),
  name        text not null,              -- the description text
  category_id uuid references categories,
  is_routine  boolean not null default false,
  active      boolean not null default true
);

-- ---------- core ledger ----------
create table if not exists transactions (
  id            uuid primary key default gen_random_uuid(),
  owner_id      uuid references auth.users default auth.uid(),
  legacy_id     integer unique,           -- item.id, for dedupe
  occurred_on   date,                     -- from year/month/day
  purchase_date date,                     -- original purchase date (credit)
  management_date date,                   -- data_gerencial (adjusted for billing)
  amount        numeric(14,2) not null,   -- signed; negative = expense
  currency      text not null default 'CAD',
  direction     text check (direction in ('income','expense')),
  label_id      integer references labels,
  label         text,                     -- denorm label.name for fast search
  category_id   uuid references categories, -- denorm from label.category_id
  details       text,                     -- merchant / payee
  notes         text,                     -- free-text memo (was "operation")
  account_id    uuid references accounts,
  account_raw   text,                     -- raw bank text
  card_id       integer references cards,
  bill_cycle    text,                     -- code_bill
  installments  text,
  cleared       boolean not null default true,
  cleared_on    date,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz
);
create index if not exists ix_tx_owner_date  on transactions (owner_id, occurred_on);
create index if not exists ix_tx_category    on transactions (category_id);
create index if not exists ix_tx_account     on transactions (account_id);
create index if not exists ix_tx_label       on transactions (label_id);
create index if not exists ix_tx_legacy      on transactions (legacy_id);

-- ---------- transaction audit log ----------
-- Mirrors the audit_log.csv pattern: captures INSERT/UPDATE/DELETE with
-- full JSON snapshots of the row before and after each change.
-- The Postgres trigger (created below) populates this automatically.
create table if not exists transaction_audit (
  id               bigserial primary key,
  transaction_id   uuid,                  -- transactions.id (may be null on DELETE)
  legacy_id        integer,               -- transactions.legacy_id for traceability
  operation        text not null check (operation in ('INSERT','UPDATE','DELETE')),
  previous_data    jsonb,                 -- full row before change (null on INSERT)
  new_data         jsonb,                 -- full row after change (null on DELETE)
  operated_at      timestamptz not null default now(),
  operated_by      uuid                   -- auth.uid() of the API caller, if available
);
create index if not exists ix_audit_tx  on transaction_audit (transaction_id);
create index if not exists ix_audit_leg on transaction_audit (legacy_id);
create index if not exists ix_audit_ts  on transaction_audit (operated_at);

-- Trigger function
create or replace function fn_audit_transactions()
returns trigger language plpgsql security definer as $$
begin
  if (TG_OP = 'INSERT') then
    insert into transaction_audit (transaction_id, legacy_id, operation, new_data)
    values (NEW.id, NEW.legacy_id, 'INSERT', to_jsonb(NEW));
    return NEW;
  elsif (TG_OP = 'UPDATE') then
    insert into transaction_audit (transaction_id, legacy_id, operation, previous_data, new_data)
    values (NEW.id, NEW.legacy_id, 'UPDATE', to_jsonb(OLD), to_jsonb(NEW));
    return NEW;
  elsif (TG_OP = 'DELETE') then
    insert into transaction_audit (transaction_id, legacy_id, operation, previous_data)
    values (OLD.id, OLD.legacy_id, 'DELETE', to_jsonb(OLD));
    return OLD;
  end if;
end;
$$;

create trigger trg_audit_transactions
  after insert or update or delete on transactions
  for each row execute function fn_audit_transactions();

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

create table if not exists shared_category_rules (
  id            uuid primary key default gen_random_uuid(),
  match_type    text not null check (match_type in ('merchant','keyword')),
  pattern       text not null,
  category_name text not null,
  confidence    integer not null default 1,
  created_at    timestamptz not null default now(),
  unique (match_type, pattern)
);

-- ---------- Row Level Security ----------
alter table cards              enable row level security;
alter table accounts           enable row level security;
alter table categories         enable row level security;
alter table labels             enable row level security;
alter table transactions       enable row level security;
alter table transaction_audit  enable row level security;
alter table tasks              enable row level security;
alter table mood_entries       enable row level security;
alter table agent_memory       enable row level security;
alter table category_rules     enable row level security;
alter table shared_category_rules enable row level security;

-- Owner-scoped policy for all personal tables
do $$
declare t text;
begin
  foreach t in array array['cards','accounts','categories','labels','transactions',
                           'tasks','mood_entries','agent_memory','category_rules']
  loop
    execute format($f$
      create policy %1$I_owner_all on %1$I
        for all to authenticated
        using (owner_id = auth.uid())
        with check (owner_id = auth.uid());
    $f$, t);
  end loop;
end $$;

-- Audit log: owner can only read their own rows (writes are trigger-only)
create policy transaction_audit_owner_read on transaction_audit
  for select to authenticated
  using (
    transaction_id in (
      select id from transactions where owner_id = auth.uid()
    )
  );

-- Shared rules: any authenticated user can read and upsert
create policy shared_rules_read   on shared_category_rules for select to authenticated using (true);
create policy shared_rules_write  on shared_category_rules for insert to authenticated with check (true);
create policy shared_rules_update on shared_category_rules for update to authenticated using (true);

