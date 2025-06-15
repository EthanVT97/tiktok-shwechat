-- Users Table
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  tiktok_id text unique,
  username text,
  display_name text,
  avatar_url text,
  created_at timestamp default now()
);

-- Properties Table
create table if not exists properties (
  id uuid primary key default gen_random_uuid(),
  owner_id text,
  title text,
  description text,
  created_at timestamp default now()
);
