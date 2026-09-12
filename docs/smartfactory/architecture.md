# SmartFactory Architecture

## Overview

SmartFactory is an IoT monitoring platform for small manufacturing facilities. It runs entirely on-premise with no cloud dependency.

## System Components

- **Edge Hub**: Raspberry Pi 4 (4GB RAM) running Debian, hosts all services
- **Sensors**: Modbus RTU devices connected via RS-485 adapter
- **Backend**: Python/FastAPI with SQLAlchemy async ORM, SQLite database
- **Frontend**: React/Vite dashboard optimized for factory floor displays
- **Alerts**: Threshold-based alert engine with cooldown periods

## Data Flow

Modbus Sensor → RS-485 Bus → Polling Service → FastAPI Handler → SQLite → Alert Engine → Dashboard

## Key Constraints

- All processing happens on the edge device (no cloud)
- 4GB RAM budget shared across all services
- Must tolerate power interruptions gracefully
- Dashboard must be readable under industrial lighting
