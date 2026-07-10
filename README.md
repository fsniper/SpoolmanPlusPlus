<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/Donkie/Spoolman/assets/2332094/4e6e80ac-c7be-4ad2-9a33-dedc1b5ba30e">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/Donkie/Spoolman/assets/2332094/3c120b3a-1422-42f6-a16b-8d5a07c33000">
  <img alt="Icon of a filament spool" src="https://github.com/Donkie/Spoolman/assets/2332094/3c120b3a-1422-42f6-a16b-8d5a07c33000">
</picture>

<br/>

# SpoolmanPlusPlus

> **This is a fork of [Spoolman](https://github.com/Donkie/Spoolman) by Donkie, extended with full 3D Print Management capabilities.**
> The project has been renamed to **SpoolmanPlusPlus** to reflect the added functionality.
> All credit for the original filament management foundation goes to the Spoolman contributors.

_Keep track of your inventory of 3D-printer filament spools — and manage your entire print workflow._

SpoolmanPlusPlus is a self-hosted web service designed to help you efficiently manage your 3D printer filament spools, monitor their usage, and now also manage your full print lifecycle — from projects and build plates to individual print jobs and printers. It acts as a centralized database that seamlessly integrates with popular 3D printing software like [OctoPrint](https://octoprint.org/) and [Klipper](https://www.klipper3d.org/)/[Moonraker](https://moonraker.readthedocs.io/en/latest/).

[![GitHub Repository](https://img.shields.io/badge/SpoolmanPlusPlus-GitHub-blue?logo=github)](https://github.com/fsniper/SpoolmanPlusPlus)
[![Upstream: Spoolman](https://img.shields.io/badge/Upstream-Spoolman-green?link=https%3A%2F%2Fgithub.com%2FDonkie%2FSpoolman)](https://github.com/Donkie/Spoolman)

---

## ✨ What's New in SpoolmanPlusPlus

SpoolmanPlusPlus adds a complete **Print Management** layer on top of the original Spoolman:

### 🖨️ Printer Management
Register and manage your physical printers with model, location, and notes. Print jobs are linked directly to a specific printer via a searchable dropdown — no more free-text entries.

### 📁 Projects
Organise your 3D prints into Projects. Group related plates and print jobs under a single project for better workflow tracking.

### 🗂️ Build Plates
Track individual build plate configurations per project — including the `.gcode` file path, estimated filament weight, and estimated print time.

### 📋 Print Jobs
Record every print job with:
- Linked **project**, **plate**, and **printer**
- Job **status** (`Queued` → `In Progress` → `Successful` / `Failed` / `Canceled`)
- **Start and end times**
- **Per-spool filament usage** (multiple spools per job)
- **Automatic weight deduction**: when a job is marked `Successful`, the used filament weight is automatically deducted from each linked spool's remaining weight

### 🗂️ Grouped Navigation
The sidebar navigation is now organised into two collapsible groups:
- **Spool Management** — Spools, Filaments, Vendors, Locations
- **Print Management** — Projects, Plates, Print Jobs, Printers

---

## Original Spoolman Features

* **Filament Management**: Keep comprehensive records of filament types, manufacturers, and individual spools.
* **API Integration**: The [REST API](https://donkie.github.io/Spoolman/) allows easy integration with other software, facilitating automated workflows and data exchange.
* **Real-Time Updates**: Stay informed with live spool updates through WebSockets, providing immediate feedback during printing operations.
* **Central Filament Database**: A community-supported database of manufacturers and filaments simplifies adding new spools to your inventory. Contribute by heading to [SpoolmanDB](https://github.com/Donkie/SpoolmanDB).
* **Web-Based Client**: Includes a built-in web client to manage data effortlessly:
  * View, create, edit, and delete filament data.
  * Add custom fields to tailor information to your specific needs.
  * Print labels with QR codes for easy spool identification and tracking.
  * Contribute to its translation into 18 languages via [Weblate](https://hosted.weblate.org/projects/spoolman/).
* **Database Support**: SQLite, PostgreSQL, MySQL, and CockroachDB.
* **Multi-Printer Management**: Handles spool updates from several printers simultaneously.
* **Advanced Monitoring**: Integrate with [Prometheus](https://prometheus.io/) for detailed historical analysis of filament usage. See the [Wiki](https://github.com/Donkie/Spoolman/wiki/Filament-Usage-History).

**Spoolman integrates with:**
  * [Moonraker](https://moonraker.readthedocs.io/en/latest/configuration/#spoolman) and most front-ends (Fluidd, KlipperScreen, Mainsail, ...)
  * [OctoPrint](https://github.com/mdziekon/octoprint-spoolman)
  * [OctoEverywhere](https://octoeverywhere.com/spoolman?source=github_spoolman)
  * [Home Assistant](https://github.com/Disane87/spoolman-homeassistant)
  * [MCP Server](https://github.com/Disane87/spoolman-mcp) — Manage your filament inventory through AI assistants like Claude using the Model Context Protocol

---

## Installation

Please see the [Installation page on the upstream Spoolman Wiki](https://github.com/Donkie/Spoolman/wiki/Installation) for base installation instructions. SpoolmanPlusPlus follows the same setup process.

After installing, run the database migrations to activate the Print Management features:

```bash
uv run alembic upgrade head
```

---

## API

The Print Management entities are available at the following REST endpoints:

| Resource     | Endpoint                    |
|--------------|-----------------------------|
| Projects     | `GET/POST /api/v1/project`  |
| Plates       | `GET/POST /api/v1/plate`    |
| Print Jobs   | `GET/POST /api/v1/print_job`|
| Printers     | `GET/POST /api/v1/printer`  |

All endpoints support full CRUD and WebSocket live updates.

---

## License

This project inherits the license from the upstream [Spoolman](https://github.com/Donkie/Spoolman) project. See [LICENSE](LICENSE) for details.
