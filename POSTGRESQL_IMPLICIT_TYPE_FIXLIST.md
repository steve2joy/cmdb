# PostgreSQL Implicit Type Fixlist

## Scope

This document tracks PostgreSQL compatibility fixes for implicit type conversion issues that were previously tolerated by MySQL.

Current focus:

1. Shared query helpers
2. ACL
3. common-setting
4. CMDB history / preference
5. CMDB ci_type / relation
6. auto discovery

## Root Cause

The codebase contains several patterns that are unsafe under PostgreSQL:

- Raw request parameters are passed into ORM filters without type normalization
- Boolean switches rely on Python truthiness instead of explicit parsing
- Dynamic query builders compare integer columns with empty strings
- Generic search helpers build `column == value` predicates from untyped kwargs

## Fix Order

### Phase 1: Shared Query Helpers

- [x] Normalize integer / float / boolean filter values in `cmdb-api/api/lib/database.py`
- [x] Normalize `__func_in___key_*` list filters in `cmdb-api/api/lib/database.py`
- [x] Normalize dynamic `kwargs` filters in `cmdb-api/api/lib/mixin.py`
- [x] Reuse a shared parsing rule instead of duplicating ad hoc conversions

### Phase 2: ACL

- [x] Normalize `resource_type_id` / `uid` in trigger resource lookup
- [x] Normalize `resource_type_id` in batch permission grant / revoke
- [x] Normalize `parent_id` / `child_ids` in role relation operations
- [x] Normalize `type_id` / `uid` in resource and resource group operations

### Phase 3: common-setting

- [x] Normalize `department_parent_id` and related department lookup inputs
- [x] Make employee condition builder type-aware
- [x] Stop generating `integer = ''` / `integer != ''`
- [x] Clarify integer `block` semantics between employee and ACL user models

### Phase 4: CMDB History / Preference

- [x] Normalize all history query ids before ORM filtering
- [x] Normalize preference search-option filters (`prv_id`, `ptv_id`, `type_id`)
- [x] Normalize preference ordering inputs (`type_ids`, `type_id`)
- [x] Replace truthy checks for `instance/tree/is_tree/enabled`

### Phase 5: CMDB CI Type / Relation

- [x] Normalize `source_type_id`, `target_type_ids`, `relation_type_id`
- [x] Normalize `attr_id` / `group_id` style identifiers
- [x] Replace truthy checks for `need_other`

### Phase 6: Auto Discovery

- [x] Stop passing `**request.values` directly into typed search helpers
- [x] Normalize `type_id`, `adt_id`, `adr_id`, `uid`
- [x] Replace truthy checks for `enabled`, `is_plugin`, `auto_accept`

## Validation Targets

- [x] Shared helper regression: string numbers against integer columns
- [x] ACL trigger / resource / permission flows
- [x] Employee filter conditions with numeric and empty values
- [x] CMDB history filters
- [x] Preference query and ordering APIs
- [x] Auto discovery typed queries

## Status

- [x] Document created
- [x] Shared query helper fixes completed
- [x] First-wave module fixes completed
- [x] Second-wave runtime verification completed

## Result Summary

The PostgreSQL implicit type-conversion repair pass has been completed for the shared helper layer and the highest-risk modules identified during manual testing.

Verified outcomes:

- Invalid numeric/boolean inputs no longer fall through as PostgreSQL operator errors in the fixed paths
- `common-setting` invalid numeric filters now return clean parameter-level errors instead of `500`
- ACL resource-group and auto-discovery typed queries no longer leak raw PostgreSQL type mismatch errors
- The main PostgreSQL regressions uncovered during runtime testing have been fixed and re-verified

Notes:

- This document tracks the implicit type-conversion work specifically
- Additional PostgreSQL runtime fixes outside this theme are tracked in `PROJECT_STATUS_AND_HANDOFF.md` and `POSTGRESQL_MIGRATION_EXECUTION_PLAN.md`
