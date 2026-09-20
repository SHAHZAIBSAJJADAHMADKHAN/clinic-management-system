export const config = Object.freeze({
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL ?? '',
})
