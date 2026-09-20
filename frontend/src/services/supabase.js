import { createClient } from '@supabase/supabase-js'
const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY
// Vitest runs in a DOM shim without the browser WebSocket support Supabase realtime initializes.
export const supabase = url && key && import.meta.env.MODE !== 'test' ? createClient(url, key) : null
