#!/usr/bin/env python3
import os, json, re

OUT_DIR = os.path.expanduser("~/astra-ownable-apps/3d-bundles")
os.makedirs(OUT_DIR, exist_ok=True)

def generate_3d_bundle(app_name: str, concept: str) -> dict:
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', app_name.strip()) or "astra_3d_experience"
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Astra Sovereign 3D // {app_name}</title>
    <style>
        body {{ margin: 0; background: #050811; color: #00ffcc; font-family: monospace; }}
        #webgl-container {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 1; pointer-events: none; }}
        .content {{ position: relative; z-index: 2; padding: 4rem; max-width: 800px; margin: 0 auto; }}
        .section {{ min-height: 100vh; background: rgba(17,24,39,0.8); border: 1px solid #1f2937; padding: 2rem; margin-bottom: 2rem; border-radius: 8px; }}
        button {{ background: #00ffcc; color: #050811; border: none; padding: 12px 24px; font-weight: bold; cursor: pointer; }}
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/ScrollTrigger.min.js"></script>
</head>
<body>
    <div id="webgl-container"></div>
    <div class="content">
        <div class="section">
            <h1>ASTRA 3D // {app_name.upper()}</h1>
            <p>Concept: {concept}</p>
            <button onclick="toggleXRay()">TOGGLE X-RAY</button>
        </div>
    </div>
    <script>
        gsap.registerPlugin(ScrollTrigger);
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(0, 0, 7);
        const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.getElementById('webgl-container').appendChild(renderer.domElement);
        scene.add(new THREE.AmbientLight(0xffffff, 1));
        const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry(2, 2), new THREE.MeshStandardMaterial({{ color: 0x0b0f19, wireframe: false, emissive: 0x00f0ff, emissiveIntensity: 0.3 }}));
        scene.add(mesh);
        gsap.to(mesh.rotation, {{ x: Math.PI * 2, y: Math.PI * 4, scrollTrigger: {{ trigger: ".content", start: "top top", end: "bottom bottom", scrub: 1 }} }});
        let xray = false;
        function toggleXRay() {{ xray = !xray; mesh.material.wireframe = xray; }}
        function animate() {{ requestAnimationFrame(animate); if(!xray) mesh.rotation.y += 0.003; renderer.render(scene, camera); }}
        animate();
    </script>
</body>
</html>
"""
    file_path = os.path.join(OUT_DIR, f"{safe_name}.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return {"status": "SUCCESS", "app_name": safe_name, "saved_path": file_path}
