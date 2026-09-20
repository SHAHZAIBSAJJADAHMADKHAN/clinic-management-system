# Clinic Appointment & Patient Management System

A full-stack clinic management platform for managing doctor availability, patient appointments, clinical records, and automated communication.

The system replaces appointment coordination through calls, messages, and paper records with a centralized application built around three roles: **Patient, Doctor, and Administrator**.

[Live Application](https://clinic-management-system-qz74.vercel.app) · [API Documentation](https://clinic-management-backend-cyan.vercel.app/docs) · [Backend API](https://clinic-management-backend-cyan.vercel.app)

---

## Overview

Clinic Appointment & Patient Management System was developed to handle the complete appointment lifecycle—from discovering an available doctor to booking, confirmation, rescheduling, cancellation, and visit completion.

The application uses React for the client, FastAPI for the application API, Supabase for PostgreSQL and authentication, and n8n for asynchronous email workflows.

Scheduling and authorization rules are enforced on the server and supported by database-level constraints rather than relying only on frontend validation.

### Key capabilities

- Role-based Patient, Doctor, and Admin portals
- Doctor availability and leave management
- 30-minute appointment slot generation
- Appointment booking, confirmation, rejection, cancellation, and rescheduling
- Doctor schedule and patient history
- Private visit notes with restricted access
- Administrative clinic dashboard
- Automated transactional email workflows
- Server-side authorization and ownership checks
- Database-level double-booking protection
- Responsive interfaces for desktop, tablet, and mobile

---

## Live Deployment

| Service | URL |
| --- | --- |
| Application | [clinic-management-system-qz74.vercel.app](https://clinic-management-system-qz74.vercel.app) |
| Backend API | [clinic-management-backend-cyan.vercel.app](https://clinic-management-backend-cyan.vercel.app) |
| Swagger / OpenAPI | [API Documentation](https://clinic-management-backend-cyan.vercel.app/docs) |
| Health Check | [Backend Health](https://clinic-management-backend-cyan.vercel.app/health) |

The frontend and backend are deployed independently on Vercel. Supabase provides the production database and authentication layer.

---

## Application Roles

### Patient

Patients can browse active doctors, inspect available appointment slots, request appointments, and manage eligible bookings.

The patient portal supports:

- Doctor discovery
- Available-slot discovery
- Appointment requests
- Appointment history and details
- Cancellation and rescheduling
- Appointment status tracking
- Access to permitted visit notes

### Doctor

Doctors have a separate workspace for managing their schedules and patient appointments.

The doctor portal supports:

- Weekly availability management
- Leave management
- Pending appointment review
- Confirm and reject actions
- Daily/upcoming schedule
- Visit completion and no-show status
- Visit notes
- Permitted patient history

### Administrator

The administrative portal provides clinic-level management without exposing private clinical notes.

Administrators can:

- Create and deactivate doctors
- View and search patients
- Review clinic appointments
- Filter appointments by doctor, date, and status
- Cancel appointments
- Monitor appointment statistics from the dashboard

---

## Architecture

```text
                         ┌──────────────────────┐
                         │    React Frontend    │
                         │ Patient/Doctor/Admin │
                         └──────────┬───────────┘
                                    │
                               REST / HTTPS
                                    │
                         ┌──────────▼───────────┐
                         │   FastAPI Backend    │
                         │                     │
                         │ Auth & Authorization│
                         │ Scheduling Rules    │
                         │ Business Logic      │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │      Supabase        │
                         │ PostgreSQL + Auth    │
                         │ RLS + Constraints    │
                         └──────────┬───────────┘
                                    │
                           Automation Events
                                    │
                         ┌──────────▼───────────┐
                         │         n8n          │
                         │ Email Automation     │
                         └──────────────────────┘
```

Additional architectural notes are available in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Technology Stack

| Layer | Technologies |
| --- | --- |
| Frontend | React, JavaScript, Vite, React Router |
| Backend | Python, FastAPI, Pydantic |
| Database | PostgreSQL, Supabase |
| Authentication | Supabase Auth, JWT, JWKS |
| Automation | n8n |
| API | REST |
| Backend Testing | Pytest |
| Frontend Testing | Vitest, React Testing Library |
| Deployment | Vercel |

---

## Scheduling Model

Appointment scheduling is treated as a backend domain rule rather than a UI-only feature.

A slot is available only when it:

1. falls inside the doctor's configured availability;
2. is not affected by doctor leave;
3. is in the future;
4. is not already held by an active appointment; and
5. does not conflict with another active appointment for the patient.

Pending appointments hold their selected slot. Rejected and cancelled appointments release it.

Rescheduling releases the previous slot and moves the appointment back into the Pending state for doctor review.

PostgreSQL constraints provide additional protection against concurrent requests attempting to create conflicting appointments.

---

## Security and Privacy

Authentication is provided by Supabase Auth. The FastAPI backend validates authenticated requests using JWT/JWKS verification and applies role and ownership checks before protected operations are executed.

The authorization model is intentionally restrictive:

- Patients can access only records permitted to their account.
- Doctors can manage only appointments associated with them.
- Doctors cannot access another doctor's private patient history.
- Patients cannot perform doctor or administrator actions.
- Visit notes are restricted to authorized participants.
- Administrators do not have access to private visit-note content.

Row Level Security and backend authorization provide separate layers of protection.

Sensitive credentials are kept in environment variables and are not exposed to the frontend repository.

---

## Appointment Lifecycle

```text
Available Slot
      |
      v
   Pending
    /   \
   /     \
Confirm  Reject
  |        |
  v        v
Confirmed Rejected
  |
  +-------------------+
  |                   |
  v                   v
Completed / No-show  Cancelled
```

Cancellation and rescheduling rules are validated by the backend, including the configured cutoff before an appointment begins.

---

## Automation

Transactional communication is handled through n8n.

Application events are recorded and processed asynchronously:

```text
Application action
       ↓
Automation event
       ↓
n8n workflow
       ↓
Claim event
       ↓
Fetch recipient/context
       ↓
Route by event type
       ↓
Build email
       ↓
Send
       ↓
Mark event processed
```

The workflow is designed to support events including doctor invitations, appointment confirmations, rejections, cancellations, rescheduling, reminders, leave-related cancellations, and pending-expiration notifications.

Event deduplication and processing state are used to reduce duplicate delivery.

---

## Repository Structure

```text
clinic-management-system/
├── backend/
│   ├── app/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
├── supabase/
│   └── migrations/
│
├── n8n/
├── docs/
├── tests/
└── README.md
```

---

## Running Locally

### Requirements

Before starting the project, install:

- Python 3
- Node.js
- npm
- Git

A Supabase project is also required for database and authentication services.

### Backend

Create the backend environment file from the example:

```bash
cp backend/.env.example backend/.env
```

Install dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

Start the API:

```bash
python -m uvicorn app.main:app --reload --app-dir backend
```

The API will be available at:

```text
http://localhost:8000
```

Swagger documentation:

```text
http://localhost:8000/docs
```

### Frontend

Create the frontend environment file:

```bash
cp frontend/.env.example frontend/.env
```

Install dependencies and start Vite:

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at:

```text
http://localhost:5173
```

> `.env` files contain environment-specific configuration and must not be committed to the repository.

---

## Testing

Backend tests:

```bash
cd backend
pytest
```

Frontend tests:

```bash
cd frontend
npm test
```

Production frontend build:

```bash
cd frontend
npm run build
```

Testing covers scheduling rules, authorization boundaries, role restrictions, appointment conflicts, availability, leave handling, privacy rules, API behavior, and frontend workflows.

---

## Acceptance Criteria

The application was developed against ten end-to-end acceptance scenarios covering the main business and security requirements:

1. Appointment booking and doctor confirmation
2. Doctor creation, availability, and dashboard persistence
3. Doctor and patient double-booking prevention
4. Out-of-hours and fully booked scheduling
5. Past dates, deactivated doctors, leave, and appointment-state restrictions
6. Appointment cancellation and rescheduling
7. Invalid and overlapping availability
8. Server-side role authorization
9. Private-record isolation
10. Automated appointment processing, email communication, refresh stability, and responsive usability

These scenarios remain the final verification baseline for the project.

---

## Design

The frontend uses a responsive healthcare-oriented interface with separate experiences for each application role.

The public-facing experience includes an interactive medical/anatomy presentation, while operational screens prioritize scheduling information, status visibility, and straightforward task completion.

The interface is designed for desktop, tablet, and mobile use.

---

## Project Status

The core full-stack system is implemented and deployed, including:

- Frontend application
- FastAPI backend
- Supabase database
- Authentication
- Patient portal
- Doctor portal
- Admin portal
- Scheduling rules
- Security controls
- n8n automation infrastructure
- Production deployment

Final production verification and edge-case testing are ongoing.

---

## Author

**Shahzaib Sajjad Ahmad Khan**

Software Engineering student focused on full-stack development and AI automation.

**Core technologies used in this project:**  
React · JavaScript · Python · FastAPI · PostgreSQL · Supabase · n8n · REST APIs · JWT/JWKS

---

## License

This project was developed for educational, portfolio, and demonstration purposes.