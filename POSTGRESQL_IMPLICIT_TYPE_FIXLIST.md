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

- [ ] Normalize integer / float / boolean filter values in `cmdb-api/api/lib/database.py`
- [ ] Normalize `__func_in___key_*` list filters in `cmdb-api/api/lib/database.py`
- [ ] Normalize dynamic `kwargs` filters in `cmdb-api/api/lib/mixin.py`
- [ ] Reuse a shared parsing rule instead of duplicating ad hoc conversions

### Phase 2: ACL

- [ ] Normalize `resource_type_id` / `uid` in trigger resource lookup
- [ ] Normalize `resource_type_id` in batch permission grant / revoke
- [ ] Normalize `parent_id` / `child_ids` in role relation operations
- [ ] Normalize `type_id` / `uid` in resource and resource group operations

### Phase 3: common-setting

- [ ] Normalize `department_parent_id` and related department lookup inputs
- [ ] Make employee condition builder type-aware
- [ ] Stop generating `integer = ''` / `integer != ''`
- [ ] Clarify integer `block` semantics between employee and ACL user models

### Phase 4: CMDB History / Preference

- [ ] Normalize all history query ids before ORM filtering
- [ ] Normalize preference search-option filters (`prv_id`, `ptv_id`, `type_id`)
- [ ] Normalize preference ordering inputs (`type_ids`, `type_id`)
- [ ] Replace truthy checks for `instance/tree/is_tree/enabled`

### Phase 5: CMDB CI Type / Relation

- [ ] Normalize `source_type_id`, `target_type_ids`, `relation_type_id`
- [ ] Normalize `attr_id` / `group_id` style identifiers
- [ ] Replace truthy checks for `need_other`

### Phase 6: Auto Discovery

- [ ] Stop passing `**request.values` directly into typed search helpers
- [ ] Normalize `type_id`, `adt_id`, `adr_id`, `uid`
- [ ] Replace truthy checks for `enabled`, `is_plugin`, `auto_accept`

## Validation Targets

- [ ] Shared helper regression: string numbers against integer columns
- [ ] ACL trigger / resource / permission flows
- [ ] Employee filter conditions with numeric and empty values
- [ ] CMDB history filters
- [ ] Preference query and ordering APIs
- [ ] Auto discovery typed queries

## Status

- [ ] Document created
- [ ] Shared query helper fixes in progress
- [ ] First-wave module fixes in progress
