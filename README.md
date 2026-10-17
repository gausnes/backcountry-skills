# backcountry-skills

A Claude Code plugin with skills for backcountry trip analysis.

## Skills

### locate-route-from-photos

Identify where a ski tour, hike, or mountain bike ride happened by matching photo skylines to elevation data, then rebuilding the likely route from terrain, treeline, trails, and the trip's distance and vert.

See [`skills/locate-route-from-photos/SKILL.md`](skills/locate-route-from-photos/SKILL.md) for the full method. The deterministic numeric code (DEM/land-cover fetching, grid lookups, treeline, skyline search, geometry) lives in [`skills/locate-route-from-photos/scripts/`](skills/locate-route-from-photos/scripts/) as importable modules, so Claude never retypes that math from memory.

## Installation

Add this repo as a plugin in Claude Code:

```
/plugin install locate-route-from-photos --marketplace gausnes/backcountry-skills
```

Or, as two steps:

```
/plugin marketplace add gausnes/backcountry-skills
/plugin install locate-route-from-photos@backcountry-skills
```
