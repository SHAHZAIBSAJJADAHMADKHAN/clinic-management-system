import { Outlet, Route, Routes } from 'react-router-dom'

import { AppLayout } from '../layouts/AppLayout'
import { DashboardShell } from '../layouts/DashboardShell'
import { EmptyState } from '../components/ui'

import { HomePage } from '../pages/HomePage'
import { NotFoundPage } from '../pages/NotFoundPage'
import {
  SignInPage,
  SignUpPage,
  SetPasswordPage,
} from '../pages/AuthPages'

import { RequireAuth } from './Guards'

import {
  Appointments,
  Booking,
  Detail,
  Doctors,
  PatientDashboard,
} from '../pages/PatientPages'

import {
  AvailabilityManagement,
  DoctorAppointmentDetail,
  DoctorDashboard,
  DoctorSchedule,
  LeaveManagement,
  PendingRequests,
} from '../pages/DoctorPages'

import {
  AdminAppointments,
  AdminDashboard,
  AdminDoctors,
  AdminPatients,
} from '../pages/AdminPages'

function Portal({ role }) {
  const navigation =
    role === 'patient'
      ? [
          { label: 'Overview', href: '/patient' },
          { label: 'Find doctors', href: '/patient/doctors' },
          { label: 'My appointments', href: '/patient/appointments' },
        ]
      : role === 'doctor'
        ? [
            { label: 'Dashboard', href: '/doctor' },
            { label: 'Pending requests', href: '/doctor/requests' },
            { label: 'Schedule', href: '/doctor/schedule' },
            { label: 'Availability', href: '/doctor/availability' },
            { label: 'Leave', href: '/doctor/leaves' },
          ]
        : role === 'admin'
          ? [
              { label: 'Dashboard', href: '/admin' },
              { label: 'Doctors', href: '/admin/doctors' },
              { label: 'Patients', href: '/admin/patients' },
              { label: 'Appointments', href: '/admin/appointments' },
            ]
          : []

  return (
    <DashboardShell
      role={role}
      title={`${role[0].toUpperCase() + role.slice(1)} workspace`}
      navigation={navigation}
    >
      <Outlet />
    </DashboardShell>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="sign-in" element={<SignInPage />} />
      <Route path="sign-up" element={<SignUpPage />} />

      <Route
        path="set-password"
        element={<SetPasswordPage />}
      />

      <Route
        path="patient"
        element={
          <RequireAuth roles={['patient']}>
            <Portal role="patient" />
          </RequireAuth>
        }
      >
        <Route index element={<PatientDashboard />} />
        <Route path="doctors" element={<Doctors />} />
        <Route path="book/:doctorId" element={<Booking />} />
        <Route path="book" element={<Booking />} />
        <Route path="appointments" element={<Appointments />} />
        <Route path="appointments/:id" element={<Detail />} />
      </Route>

      <Route
        path="doctor"
        element={
          <RequireAuth roles={['doctor']}>
            <Portal role="doctor" />
          </RequireAuth>
        }
      >
        <Route index element={<DoctorDashboard />} />
        <Route path="requests" element={<PendingRequests />} />
        <Route path="schedule" element={<DoctorSchedule />} />
        <Route
          path="appointments/:appointmentId"
          element={<DoctorAppointmentDetail />}
        />
        <Route
          path="availability"
          element={<AvailabilityManagement />}
        />
        <Route path="leaves" element={<LeaveManagement />} />
      </Route>

      <Route
        path="admin"
        element={
          <RequireAuth roles={['admin']}>
            <Portal role="admin" />
          </RequireAuth>
        }
      >
        <Route index element={<AdminDashboard />} />
        <Route path="doctors" element={<AdminDoctors />} />
        <Route path="patients" element={<AdminPatients />} />
        <Route path="appointments" element={<AdminAppointments />} />
      </Route>

      <Route
        path="unauthorized"
        element={
          <EmptyState title="Access restricted">
            Your account does not have permission for this workspace.
          </EmptyState>
        }
      />

      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}