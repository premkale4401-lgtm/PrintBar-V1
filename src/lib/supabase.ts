/// <reference types="vite/client" />
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://achtnyfmcsttfplidjoy.supabase.co';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_VxHMheqfQgm-MfgjMZfnOg_A8AAWeQL';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
