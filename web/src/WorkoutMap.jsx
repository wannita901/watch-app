import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export default function WorkoutMap({ route }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!route?.length || !ref.current) return
    const map = L.map(ref.current, { attributionControl: true })
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
    }).addTo(map)
    const line = L.polyline(route, { color: '#2a78d6', weight: 3 }).addTo(map)
    map.fitBounds(line.getBounds(), { padding: [20, 20] })
    return () => map.remove()
  }, [route])
  if (!route?.length) return null
  return <div ref={ref} className="workout-map" />
}
