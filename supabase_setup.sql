-- Run this once in the Supabase dashboard SQL editor
-- Project: hqwxrvfqcdnlgxutbttq (reused from perspectives-app)

create table if not exists cool_spots (
  id            uuid default gen_random_uuid() primary key,
  lat           double precision not null,
  lng           double precision not null,
  description   text not null,
  category      text not null check (category in ('shade','water','park','cool_building','other')),
  city          text,
  neighbourhood text,
  upvotes       integer default 0,
  flagged       boolean default false,   -- Day 16/20 moderation (plan-act2 T4)
  created_at    timestamptz default now()
);

-- If the table already exists from an earlier run, add the moderation column:
alter table cool_spots add column if not exists flagged boolean default false;

-- anyone can read, anyone can add (fully anonymous UGC)
alter table cool_spots enable row level security;

create policy "public read"   on cool_spots for select using (true);
create policy "public insert" on cool_spots for insert with check (true);
create policy "public upvote" on cool_spots for update using (true);

-- index for bounding box queries
create index if not exists cool_spots_lat_lng_idx on cool_spots (lat, lng);
