{% autoescape off %}# FynBus IT statistics — guide for Claude

This guide explains a JSON document with one year of IT helpdesk and IT
operations statistics from FynBus (a Danish public bus company). It is
written for Claude — for example Claude Motion, making an animated
presentation — but works for any reader.

## Fetching the data

- **Data:** {{ data_url }}
- Format: JSON (UTF-8), no authentication needed. The link is private:
  do not repeat it in anything you produce.
- The numbers are calculated fresh on every fetch. Helpdesk data is synced
  from ManageEngine ServiceDesk Plus every 5 minutes.
- This link expires {{ link.expires_at|date:"Y-m-d" }}.

## How the document is organised

All keys are English and stable; human-facing labels (weekdays, categories,
buckets) are Danish. Units are in the key names: `_hours`, `_percent`,
`_days`, `count`. Check `schema` = `fynbus-chronicle/statistics` and
`schema_version` = 1.

| Path | What it holds |
|---|---|
| `period` | `start`, `end` (ISO 8601, Europe/Copenhagen) and `days` (365, rolling). |
| `sources` | Where the numbers come from and `helpdesk_last_sync`. |
| `definitions` | Danish one-line definitions of the terms below. Respect them. |
| `helpdesk.summary` | `tickets_created`, `tickets_solved`, `tickets_cancelled`, `distinct_requesters` (colleagues who wrote in), `avg_tickets_per_month`, `avg_tickets_per_requester`, `open_now`. |
| `helpdesk.busiest` | Busiest `weekday` (Danish name) and `hour` (0–23, local time). |
| `helpdesk.weekday_average` | New tickets on an average Monday, Tuesday, … (`avg_new_tickets`). |
| `helpdesk.hourly_heatmap` | 7 `rows` (Mandag … Søndag) × 24 hours: `counts` = tickets in the period, `avg_per_day` = average per such day. |
| `helpdesk.resolution_time` | `median_hours`, `mean_hours`, `p90_hours`, `solved_within_24h_percent`, ready-made Danish `display` strings, and a 7-bucket `distribution` (`percent` of solved tickets). |
| `helpdesk.weekly` | 52 weeks: `week` (e.g. "U41"), `week_start`, `created`, `solved`, `open_at_week_end`. |
| `helpdesk.categories` | Share per category among categorised tickets, plus `uncategorised_percent`. |
| `helpdesk.solved_by_technician` | Solved tickets per technician (`count`, `percent`). |
| `helpdesk.open_by_age` | Open tickets by age bucket, with a suggested `color` per bucket. |
| `chronicle.priority_tasks` | The IT team's prioritised tasks: created, completed, active, median lifetime, per month. |
| `chronicle.incidents` | Outages and incidents ("nedbrud"): total, per month, by severity and type. |

## Reading the numbers correctly

- **Solved** means closed and not cancelled.
- **Resolution time is calendar time**, nights and weekends included.
  The median is the typical ticket; the mean is pulled far up by a few
  tickets open for weeks. Present the median as the headline and use the
  gap to the mean as a story point, not as a contradiction.
- **Open per week** is reconstructed from each ticket's open and close
  times; deleted tickets are missing, so older weeks can be slightly low.
- **Categories:** if `uncategorised_percent` is above 50, the category
  split rests on very few tickets. Do not present it as representative;
  at most mention that categorisation has just started.
- "Anonymiseret tekniker" is a former employee anonymised by ServiceDesk.
- Requesters are counted only; no names of colleagues who wrote in are
  included, and none should be invented.

## Suggested storyline for an animated presentation

1. **Title:** "IT-helpdesk — de seneste 12 måneder" with the period.
2. **The year in numbers:** tickets created, colleagues who wrote in,
   average per month, tickets open now. Count the numbers up.
3. **The weekly rhythm:** `weekday_average` as bars; call out the busiest
   day and that weekends are almost silent.
4. **The daily rhythm:** the heatmap, revealed hour by hour; call out the
   busiest hour.
5. **How fast:** median vs. mean, then the distribution; end on the share
   solved within a day.
6. **The flow:** `weekly` created vs. solved, and `open_at_week_end` as a
   line — is the backlog growing or shrinking?
7. **Who solves it:** `solved_by_technician` as shares.
8. **Backlog age:** `open_by_age` using the supplied colours.
9. **Beyond the helpdesk:** priority tasks and incidents from
   `chronicle`.
10. **Close** with one takeaway drawn only from the data.

## Style

- Write all on-screen text in **Danish**. Danish number format: decimal
  comma (2,2 dage), thousands with a dot (1.117), "kl. 09–10".
- Use only numbers from the document; round sensibly, never extrapolate.
- State the period somewhere visible.
{% endautoescape %}
