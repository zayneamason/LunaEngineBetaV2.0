-- Add project scope column to quests table.
-- Nullable: existing unscoped quests remain NULL.
-- New quests created for a project get the slug (e.g. 'kinoni-ict-hub').
ALTER TABLE quests ADD COLUMN project TEXT DEFAULT NULL;
