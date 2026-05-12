export interface RegionBounds {
  lon_min: number
  lon_max: number
  lat_min: number
  lat_max: number
}

export interface RegionInfo {
  key: string
  display_name: string
  bounds: RegionBounds
  has_dataset: boolean
}
