export interface Item {
  id: string
  name: string
  qty_text: string
  note: string | null
  created_at: string
}

export interface Box {
  id: string
  label: string
  name: string
  barcode: string | null
  photo_url: string | null
  location_text: string | null
  gps_lat: number | null
  gps_lng: number | null
  color_a: string
  color_b: string
  source: string
  created_at: string
  updated_at: string
  items: Item[]
  photos: string[]
  audios: string[]
}

export interface Me {
  user_id: string
  email: string | null
  lang: string
  gps_enabled: boolean
  credit_balance: number
  used: number
  box_count: number
  item_count: number
}

export interface ItemDraft {
  name: string
  qty_text: string
}

export interface InterpretResult {
  intent: 'ingest' | 'query' | 'operation'
  box_label: string | null
  box: Box | null
  items: ItemDraft[]
  location_text: string | null
  language: string
  next_label: string
}

export interface AgentAction {
  tool: string
  args: Record<string, unknown>
  summary: string
}

export interface AgentResp {
  type: 'message' | 'confirm'
  text: string
  actions?: AgentAction[]
}

export interface BoxRef {
  id: string
  label: string
  name: string
  location_text: string | null
  color_a: string
  color_b: string
  gps_lat: number | null
  gps_lng: number | null
}

export type Screen = 'onboarding' | 'home' | 'ask' | 'boxes' | 'boxdetail' | 'settings' | 'camera' | 'scan'

export interface RecogItem {
  name: string
  qty_text: string
  confidence: 'high' | 'medium' | 'low'
}

export interface RecogResult {
  box_label: string | null
  box_exists: boolean
  items: RecogItem[]
  next_label: string
}

export type EntryPhase = 'idle' | 'input' | 'recording' | 'parsing' | 'confirm' | 'askbox' | 'edit' | 'done'
