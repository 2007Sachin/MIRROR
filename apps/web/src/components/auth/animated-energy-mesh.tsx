"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

type AnimatedEnergyMeshProps = {
  energized?: boolean;
  variant?: "default" | "compact";
};

const meshVertexShader = /* glsl */ `
  uniform float uTime;
  uniform float uEnergy;
  varying vec3 vPosition;
  varying vec3 vNormal;

  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

  float snoise(vec3 v) {
    const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
      i.z + vec4(0.0, i1.z, i2.z, 1.0))
      + i.y + vec4(0.0, i1.y, i2.y, 1.0))
      + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0) * 2.0 + 1.0;
    vec4 s1 = floor(b1) * 2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m *= m;
    return 42.0 * dot(m * m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
  }

  void main() {
    vec3 direction = normalize(position);
    float slowTime = uTime * 0.12;
    float broad = snoise(direction * 1.65 + vec3(slowTime, -slowTime * 0.7, slowTime * 0.45));
    float detail = snoise(direction * 3.8 + vec3(-slowTime * 0.55, slowTime * 0.38, slowTime * 0.8));
    float contour = sin(direction.x * 5.0 - uTime * 0.17) * sin(direction.y * 4.0 + uTime * 0.13) * 0.35;
    float breath = sin(uTime * 0.72) * 0.045;
    float displacement = broad * (0.185 + uEnergy * 0.03) + detail * 0.068 + contour * 0.04 + breath;
    vec3 displaced = position + direction * displacement;
    vPosition = displaced;
    vNormal = normalize(normalMatrix * direction);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
  }
`;

const meshFragmentShader = /* glsl */ `
  uniform float uEnergy;
  uniform float uReveal;
  varying vec3 vPosition;
  varying vec3 vNormal;

  void main() {
    vec3 cyan = vec3(0.02, 0.48, 1.0);
    vec3 violet = vec3(0.42, 0.12, 1.0);
    vec3 magenta = vec3(1.0, 0.02, 0.74);
    float sweep = smoothstep(-1.35, 1.25, vPosition.x - vPosition.y * 0.22);
    vec3 color = mix(cyan, violet, smoothstep(0.08, 0.58, sweep));
    color = mix(color, magenta, smoothstep(0.48, 0.98, sweep));
    vec3 viewDirection = normalize(cameraPosition - vPosition);
    float rim = pow(1.0 - abs(dot(normalize(vNormal), viewDirection)), 1.7);
    float lowerGlow = smoothstep(0.75, -1.2, vPosition.y) * smoothstep(-0.2, 1.3, vPosition.x);
    float intensity = 0.68 + rim * 1.65 + lowerGlow * 0.48 + uEnergy * 0.12;
    gl_FragColor = vec4(color * intensity, (0.46 + rim * 0.46) * uReveal);
  }
`;

const particleVertexShader = /* glsl */ `
  uniform float uTime;
  uniform float uPixelRatio;
  varying float vColorMix;
  varying float vAlpha;
  void main() {
    float angle = uTime * (0.025 + fract(position.y * 3.17) * 0.018);
    float c = cos(angle);
    float s = sin(angle);
    vec3 p = position;
    p.xz = mat2(c, -s, s, c) * p.xz;
    p.y += sin(uTime * 0.18 + position.x * 3.0) * 0.035;
    vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mvPosition;
    gl_PointSize = (1.25 + fract(position.x * 12.7) * 1.7) * uPixelRatio * (5.5 / -mvPosition.z);
    vColorMix = smoothstep(-2.0, 2.0, p.x);
    vAlpha = 0.3 + fract(position.z * 8.3) * 0.62;
  }
`;

const particleFragmentShader = /* glsl */ `
  uniform float uReveal;
  varying float vColorMix;
  varying float vAlpha;
  void main() {
    float distanceToCenter = length(gl_PointCoord - vec2(0.5));
    if (distanceToCenter > 0.5) discard;
    float glow = 1.0 - smoothstep(0.08, 0.5, distanceToCenter);
    vec3 color = mix(vec3(0.03, 0.48, 1.0), vec3(1.0, 0.02, 0.74), vColorMix);
    gl_FragColor = vec4(color * (1.15 + glow), glow * vAlpha * uReveal);
  }
`;

function createMeshGrid() {
  const positions: number[] = [];
  const segments = 112;
  const latitudeLines = 54;
  const longitudeLines = 76;
  const radius = 1.48;

  const point = (theta: number, phi: number) => [
    radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  ];

  for (let lat = 1; lat < latitudeLines; lat += 1) {
    const phi = (lat / latitudeLines) * Math.PI;
    for (let step = 0; step < segments; step += 1) {
      const thetaA = (step / segments) * Math.PI * 2;
      const thetaB = ((step + 1) / segments) * Math.PI * 2;
      positions.push(...point(thetaA, phi), ...point(thetaB, phi));
    }
  }

  for (let lon = 0; lon < longitudeLines; lon += 1) {
    const theta = (lon / longitudeLines) * Math.PI * 2;
    for (let step = 0; step < segments; step += 1) {
      const phiA = (step / segments) * Math.PI;
      const phiB = ((step + 1) / segments) * Math.PI;
      positions.push(...point(theta, phiA), ...point(theta, phiB));
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.computeBoundingSphere();
  return geometry;
}

function createParticles(count: number) {
  const positions = new Float32Array(count * 3);
  for (let index = 0; index < count; index += 1) {
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    const y = 1 - (index / Math.max(1, count - 1)) * 2;
    const radiusAtY = Math.sqrt(1 - y * y);
    const angle = goldenAngle * index;
    const shell = 1.7 + ((index * 47) % 100) / 185;
    positions[index * 3] = Math.cos(angle) * radiusAtY * shell;
    positions[index * 3 + 1] = y * shell;
    positions[index * 3 + 2] = Math.sin(angle) * radiusAtY * shell;
  }
  return positions;
}

function EnergyScene({ energized, compact, reducedMotion, pointer }: AnimatedEnergyMeshProps & {
  compact: boolean;
  reducedMotion: boolean;
  pointer: React.RefObject<THREE.Vector2>;
}) {
  const group = useRef<THREE.Group>(null);
  const ring = useRef<THREE.Mesh>(null);
  const ringMaterial = useRef<THREE.MeshBasicMaterial>(null);
  const meshMaterial = useRef<THREE.ShaderMaterial>(null);
  const particleMaterial = useRef<THREE.ShaderMaterial>(null);
  const introTime = useRef(0);
  const grid = useMemo(() => createMeshGrid(), []);
  const particlePositions = useMemo(() => createParticles(compact ? 120 : 360), [compact]);
  const meshUniforms = useMemo(() => ({ uTime: { value: reducedMotion ? 3.4 : 0 }, uEnergy: { value: 0 }, uReveal: { value: reducedMotion ? 1 : 0 } }), [reducedMotion]);
  const particleUniforms = useMemo(() => ({ uTime: { value: 0 }, uPixelRatio: { value: 1 }, uReveal: { value: reducedMotion ? 1 : 0 } }), [reducedMotion]);

  useEffect(() => () => grid.dispose(), [grid]);

  useFrame(({ clock, gl }, delta) => {
    const elapsed = reducedMotion ? 3.4 : clock.getElapsedTime();
    introTime.current = reducedMotion ? 3 : Math.min(3, introTime.current + delta);
    const introProgress = THREE.MathUtils.smoothstep(introTime.current, 0.12, 2.45);
    if (meshMaterial.current) {
      meshMaterial.current.uniforms.uTime.value = elapsed;
      meshMaterial.current.uniforms.uReveal.value = introProgress;
      meshMaterial.current.uniforms.uEnergy.value = THREE.MathUtils.damp(
        meshMaterial.current.uniforms.uEnergy.value,
        energized ? 1 : 0,
        3.2,
        delta,
      );
    }
    if (particleMaterial.current) {
      particleMaterial.current.uniforms.uTime.value = elapsed;
      particleMaterial.current.uniforms.uPixelRatio.value = Math.min(gl.getPixelRatio(), 1.75);
      particleMaterial.current.uniforms.uReveal.value = THREE.MathUtils.smoothstep(introTime.current, 0.85, 2.8);
    }
    if (group.current) {
      const targetX = pointer.current.y * 0.16 - 0.08;
      const targetY = pointer.current.x * 0.2 - 0.16;
      group.current.rotation.x = THREE.MathUtils.damp(group.current.rotation.x, targetX, 2.6, delta);
      group.current.rotation.y = THREE.MathUtils.damp(group.current.rotation.y, targetY, 2.6, delta);
      group.current.rotation.z = reducedMotion ? -0.12 : -0.12 + Math.sin(elapsed * 0.11) * 0.045;
      const introScale = reducedMotion ? 1 : 0.68 + introProgress * 0.32;
      const scale = introScale * (1 + (energized ? 0.018 : 0) + (reducedMotion ? 0 : Math.sin(elapsed * 0.72) * 0.01));
      group.current.scale.setScalar(THREE.MathUtils.damp(group.current.scale.x, scale, 2.8, delta));
      group.current.position.y = reducedMotion ? 0 : Math.sin(elapsed * 0.27) * 0.022;
    }
    if (ring.current && ringMaterial.current) {
      const ringPulse = reducedMotion ? 0 : (Math.sin(elapsed * 0.62) + 1) * 0.5;
      const ringScale = 0.72 + introProgress * 0.38 + ringPulse * 0.015;
      ring.current.scale.setScalar(ringScale);
      ringMaterial.current.opacity = reducedMotion ? 0.07 : (1 - introProgress) * 0.42 + 0.045 + ringPulse * 0.025;
    }
  });

  return (
    <>
      <mesh ref={ring} position={[0, 0, -0.3]}>
        <ringGeometry args={[1.72, 1.735, 128]} />
        <meshBasicMaterial
          ref={ringMaterial}
          color="#d9cbff"
          transparent
          opacity={reducedMotion ? 0.07 : 0}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </mesh>
      <group ref={group} rotation={[-0.08, -0.16, -0.12]} scale={reducedMotion ? 1 : 0.68}>
        <lineSegments geometry={grid}>
        <shaderMaterial
          ref={meshMaterial}
          vertexShader={meshVertexShader}
          fragmentShader={meshFragmentShader}
          uniforms={meshUniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
        </lineSegments>
        {!reducedMotion && (
          <points>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[particlePositions, 3]} />
          </bufferGeometry>
          <shaderMaterial
            ref={particleMaterial}
            vertexShader={particleVertexShader}
            fragmentShader={particleFragmentShader}
            uniforms={particleUniforms}
            transparent
            depthWrite={false}
            blending={THREE.AdditiveBlending}
            toneMapped={false}
          />
          </points>
        )}
      </group>
    </>
  );
}

export function AnimatedEnergyMesh({ energized = false, variant = "default" }: AnimatedEnergyMeshProps) {
  const [smallViewport, setSmallViewport] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const pointer = useRef(new THREE.Vector2(0, 0));
  const compact = variant === "compact" || smallViewport;

  useEffect(() => {
    const compactQuery = window.matchMedia("(max-width: 900px)");
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => {
      setSmallViewport(compactQuery.matches);
      setReducedMotion(motionQuery.matches);
    };
    sync();
    compactQuery.addEventListener("change", sync);
    motionQuery.addEventListener("change", sync);
    return () => {
      compactQuery.removeEventListener("change", sync);
      motionQuery.removeEventListener("change", sync);
    };
  }, []);

  function updatePointer(event: React.PointerEvent<HTMLDivElement>) {
    if (reducedMotion) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    pointer.current.set(
      ((event.clientX - bounds.left) / bounds.width) * 2 - 1,
      -(((event.clientY - bounds.top) / bounds.height) * 2 - 1),
    );
  }

  return (
    <div
      className={`energy-mesh-stage ${variant === "compact" ? "is-compact" : ""}`}
      aria-hidden="true"
      onPointerMove={updatePointer}
      onPointerLeave={() => pointer.current.set(0, 0)}
    >
      <div className="energy-mesh-aura" />
      <div className="energy-mesh-beam" />
      <Canvas
        className="energy-mesh-canvas"
        camera={{ position: [0, 0, compact ? 6.6 : 8.35], fov: compact ? 47 : 43 }}
        dpr={compact ? [1, 1.25] : [1, 1.75]}
        frameloop={reducedMotion ? "demand" : "always"}
        gl={{ alpha: true, antialias: !compact, powerPreference: "high-performance" }}
      >
        <EnergyScene
          energized={energized}
          compact={compact}
          reducedMotion={reducedMotion}
          pointer={pointer}
        />
      </Canvas>
      <div className="energy-mesh-vignette" />
    </div>
  );
}
