-- Turkish Tutor Bot — Supabase Schema
-- Run this in Supabase → SQL Editor

create table if not exists profile (
    user_id     bigint primary key,
    level       text    default 'A1',
    xp          integer default 0,
    streak      integer default 0,
    last_active date,
    current_focus text   default 'التحية والمفردات الأساسية'
);

create table if not exists messages (
    id          bigserial primary key,
    user_id     bigint not null,
    role        text   not null check (role in ('user', 'assistant')),
    content     text   not null,
    timestamp   timestamptz default now()
);
create index if not exists messages_user_id_idx on messages (user_id, id desc);

create table if not exists weaknesses (
    id          bigserial primary key,
    user_id     bigint not null,
    topic       text   not null,
    count       integer default 1,
    last_seen   date    default current_date,
    example     text,
    unique (user_id, topic)
);

create table if not exists strengths (
    id           bigserial primary key,
    user_id      bigint not null,
    topic        text   not null,
    confirmed_at date   default current_date,
    review_due   date,
    unique (user_id, topic)
);

create table if not exists vocab_srs (
    id           bigserial primary key,
    user_id      bigint not null,
    word         text   not null,
    translation  text   not null,
    ease_factor  real   default 2.5,
    interval     integer default 1,
    due_date     date   default current_date,
    repetitions  integer default 0,
    unique (user_id, word)
);
