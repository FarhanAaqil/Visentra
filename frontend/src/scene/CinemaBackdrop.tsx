import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import type { Mood } from '../lib/store'

const PALETTE: Record<Mood, { core: number; dust: number; speed: number; pulse: number }> = {
  calm: { core: 0xfb7185, dust: 0xfad4db, speed: 0.6, pulse: 0.15 },
  alert: { core: 0xfbbf24, dust: 0xfde68a, speed: 0.9, pulse: 0.3 },
  breach: { core: 0xff1f4b, dust: 0xff8fa3, speed: 1.8, pulse: 0.75 },
}

function knotPoints(count: number): Float32Array {
  // A (3,7) torus knot: one continuous strand, the lineage drawn as a single thread.
  const pts = new Float32Array(count * 3)
  for (let i = 0; i < count; i++) {
    const t = (i / count) * Math.PI * 2
    const p = 3
    const q = 7
    const r = 2.4 + 0.9 * Math.cos(q * t)
    const jitter = () => (Math.random() - 0.5) * 0.18
    pts[i * 3] = r * Math.cos(p * t) + jitter()
    pts[i * 3 + 1] = r * Math.sin(p * t) + jitter()
    pts[i * 3 + 2] = 0.9 * Math.sin(q * t) + jitter()
  }
  return pts
}

function dustPoints(count: number): Float32Array {
  const pts = new Float32Array(count * 3)
  for (let i = 0; i < count; i++) {
    const r = 6 + Math.random() * 14
    const th = Math.random() * Math.PI * 2
    const ph = Math.acos(2 * Math.random() - 1)
    pts[i * 3] = r * Math.sin(ph) * Math.cos(th)
    pts[i * 3 + 1] = r * Math.sin(ph) * Math.sin(th) * 0.6
    pts[i * 3 + 2] = r * Math.cos(ph) - 6
  }
  return pts
}

function glowTexture(): THREE.Texture {
  const c = document.createElement('canvas')
  c.width = c.height = 64
  const g = c.getContext('2d')!
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32)
  grad.addColorStop(0, 'rgba(255,255,255,1)')
  grad.addColorStop(0.25, 'rgba(255,255,255,0.6)')
  grad.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = grad
  g.fillRect(0, 0, 64, 64)
  return new THREE.CanvasTexture(c)
}

export default function CinemaBackdrop({ mood }: { mood: Mood }) {
  const host = useRef<HTMLDivElement>(null)
  const moodRef = useRef<Mood>(mood)

  useEffect(() => {
    moodRef.current = mood
  }, [mood])

  useEffect(() => {
    const el = host.current
    if (!el) return
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
    } catch {
      return // no WebGL: the CSS gradient backdrop is enough
    }
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75))
    renderer.setSize(el.clientWidth, el.clientHeight)
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    scene.fog = new THREE.FogExp2(0x140304, 0.045)
    const camera = new THREE.PerspectiveCamera(55, el.clientWidth / el.clientHeight, 0.1, 100)
    camera.position.set(0, 0, 11)

    const sprite = glowTexture()
    const group = new THREE.Group()
    group.position.set(3.2, 0.2, 0)
    scene.add(group)

    const knotGeo = new THREE.BufferGeometry()
    knotGeo.setAttribute('position', new THREE.BufferAttribute(knotPoints(2600), 3))
    const knotMat = new THREE.PointsMaterial({
      size: 0.09,
      map: sprite,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      color: PALETTE.calm.core,
      opacity: 0.9,
    })
    group.add(new THREE.Points(knotGeo, knotMat))

    const coreGeo = new THREE.IcosahedronGeometry(1.25, 1)
    const coreMat = new THREE.MeshBasicMaterial({ color: PALETTE.calm.core, wireframe: true, transparent: true, opacity: 0.35 })
    const core = new THREE.Mesh(coreGeo, coreMat)
    group.add(core)

    const shellGeo = new THREE.IcosahedronGeometry(1.9, 0)
    const shellMat = new THREE.MeshBasicMaterial({ color: 0xfad4db, wireframe: true, transparent: true, opacity: 0.08 })
    const shell = new THREE.Mesh(shellGeo, shellMat)
    group.add(shell)

    const dustGeo = new THREE.BufferGeometry()
    dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPoints(1400), 3))
    const dustMat = new THREE.PointsMaterial({
      size: 0.07,
      map: sprite,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      color: PALETTE.calm.dust,
      opacity: 0.55,
    })
    const dust = new THREE.Points(dustGeo, dustMat)
    scene.add(dust)

    const pointer = { x: 0, y: 0 }
    const onMove = (e: PointerEvent) => {
      pointer.x = (e.clientX / window.innerWidth - 0.5) * 2
      pointer.y = (e.clientY / window.innerHeight - 0.5) * 2
    }
    const onResize = () => {
      camera.aspect = el.clientWidth / el.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(el.clientWidth, el.clientHeight)
      group.position.x = el.clientWidth < 900 ? 0 : 3.2
    }
    onResize()
    window.addEventListener('pointermove', onMove)
    window.addEventListener('resize', onResize)

    const coreColor = new THREE.Color(PALETTE.calm.core)
    const dustColor = new THREE.Color(PALETTE.calm.dust)
    const clock = new THREE.Clock()
    let speed = PALETTE.calm.speed
    let pulse = PALETTE.calm.pulse
    let frame = 0

    const tick = () => {
      const dt = Math.min(clock.getDelta(), 0.05)
      const t = clock.elapsedTime
      const target = PALETTE[moodRef.current]
      coreColor.lerp(new THREE.Color(target.core), 0.04)
      dustColor.lerp(new THREE.Color(target.dust), 0.04)
      speed += (target.speed - speed) * 0.03
      pulse += (target.pulse - pulse) * 0.03
      knotMat.color.copy(coreColor)
      coreMat.color.copy(coreColor)
      dustMat.color.copy(dustColor)

      const motion = reduced ? 0.15 : 1
      group.rotation.y += dt * 0.12 * speed * motion
      group.rotation.x = Math.sin(t * 0.2) * 0.25
      core.rotation.x += dt * 0.4 * speed * motion
      core.rotation.z -= dt * 0.25 * speed * motion
      shell.rotation.y -= dt * 0.08 * speed * motion
      const beat = 1 + Math.sin(t * 3.2 * speed) * 0.06 * pulse * motion
      core.scale.setScalar(beat)
      knotMat.size = 0.085 + 0.03 * pulse * (0.5 + 0.5 * Math.sin(t * 2.4))
      dust.rotation.y += dt * 0.015 * motion

      camera.position.x += (pointer.x * 0.8 - camera.position.x) * 0.03
      camera.position.y += (-pointer.y * 0.5 - camera.position.y) * 0.03
      camera.lookAt(0, 0, 0)
      renderer.render(scene, camera)
      frame = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('resize', onResize)
      for (const obj of [knotGeo, knotMat, coreGeo, coreMat, shellGeo, shellMat, dustGeo, dustMat, sprite]) obj.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])

  return <div ref={host} aria-hidden style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }} />
}
