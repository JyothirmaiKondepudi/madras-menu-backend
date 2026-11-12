# Organization-owned catering pricing

This is a storage model and validated configuration inputs, not a quote
calculator or a menu generator. All organizations share the same four tables;
onboarding adds rows, never tables. Subscription plans remain in the admin service.

## Tables

| Table | Purpose |
| --- | --- |
| `pricing_tiers` | Organization-specific names, display order, and base-tier marker |
| `pricing_base_rates` | Base package price per guest, minimum package charge, and inclusion description |
| `pricing_adjustments` | Conditional surcharges, optionally limited to a tier or a shared dish ID |
| `pricing_tier_additions` | Explicit included features and their prices for a particular tier |

Every row has a UUID, `org_id`, an active flag, and creation/update timestamps.
Composite foreign keys ensure additions and adjustments cannot reference
another organization's tier, even through direct SQL. Organization ownership
does not itself filter SELECTs: future endpoints must scope every operation to
the authenticated user's organization, including lookups by UUID. Configuration
input schemas reject caller-supplied organization IDs and unknown fields.

The current dish catalog is shared. An adjustment can reference that shared
identity, but its amount belongs only to the adjustment's organization. It is
a surcharge, not an ingredient cost or an automatic replacement for the base
package price. Different organizations may charge different amounts for the
same dish. Organization-specific dish libraries remain a separate integration.

## Conditions and amounts

Base rates, adjustments and additions support:

- Optional event type, service style, and diet category, using existing choice lists.
- Inclusive minimum/maximum guest counts. Minimum defaults to one; no maximum
  means unbounded.
- Required effective-from date and optional exclusive effective-until date.
- Required three-letter uppercase currency code. There is no currency conversion.

A NULL categorical condition means unrestricted. Diet is one **pricing
category**, not a representation of every attendee's dietary restrictions.
All supplied categorical conditions must match. Current models intentionally
do not accept arbitrary condition expressions, SQL, or executable formulas.

Amounts use `Numeric(12, 2)` and Decimal input validation. Base prices and
charges cannot be negative. Additions and adjustments support `guest` and
`event` charge units; hourly services and equipment already have their own
catalogs. Discounts/percentages require a separately defined calculation policy
before extending this model. A zero amount permits a feature included at no
extra charge.

Rates can be shared across events by leaving event type empty. Separate event
rates should only be configured when the business actually prices differently.
The model does not create a row for every event/dish/tier combination.

## Madras onboarding

Create the following rows **only for the explicitly selected Madras organization**:

| name | position | isBase |
| --- | --- | --- |
| Elegant | 0 | true |
| Premium | 1 | false |
| Luxury Premium | 2 | false |

Other organizations choose their own names and tier counts. There can be at
most one active base tier per organization; onboarding must ensure one exists
before enabling pricing. Names are unique ignoring case within an organization,
and positions are unique within an organization (including inactive tiers).

All tiers start from the organization's applicable base rate. Position does
not imply inheritance. Premium and Luxury Premium each have their own explicit
list of additions to the base package. If both include an extra starter, record
that feature for both tiers. Do not also configure the same feature as an
adjustment or it could be charged twice by a future calculator.

No prices are seeded because the client's rates have not been supplied. The
migration also does not infer which existing organization is Madras.

## Migration and compatibility

Revision `a7b83c91d204` follows `0b2e58333f53`. Apply through the normal Alembic
workflow (`alembic upgrade head`) or the Docker migration service. It creates
only the new pricing tables and indexes; downgrade removes only those tables.

The unrelated legacy `price_tiers` table is preserved. It lacks organization
ownership and has no ORM/API consumer in this checkout. Migrating its data
requires an explicit business-approved organization mapping; none is guessed.

## Follow-on work

Before exposing a calculation endpoint:

1. Add authenticated, organization-scoped configuration APIs and permissions.
2. Implement deterministic matching. Require exactly one applicable base rate;
   missing or ambiguous matches must require review. This model allows overlapping
   conditions; it does not silently pick a winner or enforce overlap exclusion.
3. Define adjustment stacking, package minimums, discounts, and rounding order.
4. Make package inclusions machine-readable once course counts and eligibility
   rules are agreed. Current inclusion descriptions are not executable rules.
5. Save quote line snapshots and source-rule IDs. Effective dates alone do not
   preserve history when a rate is edited. Issued quotes must never recalculate
   from mutable configuration.
6. Connect menu proposals using stable IDs; the calculator must validate package
   eligibility rather than trust generated dishes blindly.

## Validation

Run input and PostgreSQL migration/constraint tests independently of the app
suite's database fixtures:

```bash
PRICING_TEST_DATABASE_URL=postgresql+psycopg2://postgres:<password>@localhost:<port>/<test_db> \
  .venv/bin/python -m unittest discover -s tests/pricing_model -v
```

The tests create a randomly named schema inside the supplied test database and
roll it back after each test. They cover cross-organization references, distinct
organization prices, tier uniqueness, range validation, migration/model column
parity, and downgrade preservation of the legacy table. Without that environment
variable, PostgreSQL tests are skipped and input validation tests still run.
