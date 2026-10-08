-- Owner (Oct 8): ending fuel inventory per tank, read from the tank monitor at closing.
-- Each store has its own tanks (names editable in Settings). The tank NAME is copied into each day,
-- so renaming a tank later doesn't change past days.
alter table stores
    add column if not exists tanks jsonb not null
        default '["Tank 1 – Regular", "Tank 2 – Regular", "Tank 3 – Premium"]'::jsonb;

alter table daily_reports
    add column if not exists tank_inventory jsonb not null default '[]'::jsonb;  -- [{"tank": "...", "gallons": "1234.5"}]
