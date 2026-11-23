"""Render a ring escape scene locally at the final playback cadence."""
import colorsys
import math
from collections import deque


def _ball_color(hue, saturation, value):
    return tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue % 1, saturation, value)[::-1])


def _render_bouncing_ball(path, width, height, fps, duration, speed, rng, token):
    import cv2
    import numpy as np

    seed = rng.getrandbits(64)
    scene = random.Random(seed)
    direction = scene.choice((-1, 1))
    hue = scene.choice((.47, .53, .59, .73, .89)) + scene.uniform(-.035, .035)
    scale = min(1, 1080 / max(width, height))
    width, height = (max(2, round(size * scale / 2) * 2) for size in (width, height))
    unit = min(width, height) * .44
    cx, cy = width / 2, height / 2
    yy, xx = np.ogrid[:height, :width]
    distance_squared = ((xx-cx)/unit)**2 + ((yy-cy)/unit)**2
    glow = np.exp(-1.25 * distance_squared)[..., None]
    ambient = np.array(_ball_color(hue+.04, .53, .17))
    background = (np.array([17, 11, 10]) + glow * ambient).astype(np.uint8)

    radii = tuple(.35 + i * .074 for i in range(9))
    gap = math.radians(59)
    ball_radius = .035
    angles = [scene.uniform(0, math.tau) for _ in radii]
    spins = [direction * (-1 if i % 2 else 1) * scene.uniform(.42, .91) for i in range(len(radii))]
    colors = [_ball_color(hue + i * .031, .49 + i * .019, .98) for i in range(len(radii))]
    ball_color = _ball_color(hue+.43, .55, 1)
    ball_core = _ball_color(hue+.43, .14, 1)
    rate = float(fps)
    trail = deque(maxlen=max(8, round(rate*.23)))
    impacts = deque()
    escapes = {}
    subpixel = 8
    precision = 1 << subpixel

    def point(x, y):
        return round((cx+x*unit)*precision), round((cy+y*unit)*precision)

    def circle(image, x, y, radius, color, thickness=-1):
        cv2.circle(image, point(x, y), max(1, round(radius*unit*precision)),
                   color, thickness, cv2.LINE_AA, subpixel)

    def launch():
        angle = scene.uniform(0, math.tau)
        return 0.0, -.065, math.cos(angle)*.89, math.sin(angle)*.89

    def dim(color, amount):
        return tuple(round(value*amount) for value in color)

    def draw_ring(image, index, clock, opacity):
        radius = radii[index]
        center = angles[index] + spins[index]*clock
        samples = max(80, round(radius*unit*1.4))
        arc = np.linspace(center+gap/2, center+math.tau-gap/2, samples)
        coords = np.rint(np.column_stack((cx+radius*unit*np.cos(arc),
                                         cy+radius*unit*np.sin(arc)))*precision).astype(np.int32)
        color = colors[index]
        cv2.polylines(image, [coords], False, dim(color, .24*opacity),
                      max(2, round(unit*.024)), cv2.LINE_AA, subpixel)
        cv2.polylines(image, [coords], False, dim(color, opacity),
                      max(1, round(unit*.009)), cv2.LINE_AA, subpixel)
        for end in (center+gap/2, center-gap/2):
            circle(image, radius*math.cos(end), radius*math.sin(end),
                   .009, dim(color, opacity))

    x, y, vx, vy = launch()
    inner = 0
    last_reset = 0.0
    reset_at = None
    subdivisions = max(1, math.ceil(360*speed/rate))
    dt = speed/(rate*subdivisions)
    frame_count = math.ceil(duration*rate) + 2
    command = [ffmpeg(), '-y', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'bgr24',
               '-video_size', f'{width}x{height}', '-framerate', str(fps), '-i', '-',
               '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p', str(path)]
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            for frame_index in range(frame_count):
                _check(token)
                time = frame_index/rate
                if reset_at is not None and time >= reset_at:
                    x, y, vx, vy = launch()
                    inner = 0
                    last_reset = time
                    reset_at = None
                    trail.clear()
                    impacts.clear()
                    escapes.clear()

                for step in range(subdivisions):
                    clock = time*speed + step*dt
                    vy += .77*dt
                    x, y = x+vx*dt, y+vy*dt
                    distance = math.hypot(x, y)
                    if inner == len(radii):
                        if distance > 1.13 and reset_at is None:
                            reset_at = time+.46
                        continue
                    radius = radii[inner]
                    contact = radius-ball_radius
                    if distance <= contact:
                        continue
                    nx, ny = x/distance, y/distance
                    angle = math.atan2(y, x)
                    ring_angle = angles[inner]+spins[inner]*clock
                    offset = (angle-ring_angle+math.pi)%math.tau-math.pi
                    if abs(offset) < gap/2-ball_radius/radius:
                        if distance >= radius+ball_radius:
                            escapes[inner] = time
                            impacts.append((time, x, y, inner, True))
                            inner += 1
                        continue
                    outward = vx*nx+vy*ny
                    if outward > 0:
                        vx -= 1.97*outward*nx
                        vy -= 1.97*outward*ny
                        impacts.append((time, nx*radius, ny*radius, inner, False))
                    x, y = nx*contact, ny*contact

                picture = background.copy()
                fade_in = min(1, .35+(time-last_reset)*3.5)
                fade_out = min(1, (reset_at-time)*3.0) if reset_at is not None else 1
                visibility = fade_in*fade_out
                for index in range(len(radii)):
                    opacity = 1 if index >= inner else max(0, 1-(time-escapes[index])/.36)**2
                    if opacity > 0:
                        draw_ring(picture, index, time*speed, opacity*visibility)

                while impacts and time-impacts[0][0] > .45:
                    impacts.popleft()
                for start, px, py, index, escaped in impacts:
                    age = (time-start)/.45
                    accent = colors[index]
                    circle(picture, px, py, .024+age*.14, dim(accent, visibility*(1-age)**2*.64),
                           max(1, round(unit*.007)))
                    if escaped:
                        angle = math.atan2(py, px)
                        for particle in range(7):
                            spread = angle+(particle-3)*.47
                            travel = age*(.14+particle*.025)
                            circle(picture, px+math.cos(spread)*travel, py+math.sin(spread)*travel,
                                   .013*(1-age), dim(accent, visibility*(1-age)*.88))

                trail.append((x, y))
                for index, (px, py) in enumerate(trail, 1):
                    weight = index/len(trail)
                    circle(picture, px, py, ball_radius*(.16+.62*weight),
                           dim(ball_color, visibility*(.18+.68*weight**2)))
                circle(picture, x, y, ball_radius*1.66, dim(ball_color, visibility*.24))
                circle(picture, x, y, ball_radius*1.22, dim(ball_color, visibility*.61))
                circle(picture, x, y, ball_radius, dim(ball_color, visibility))
                circle(picture, x-.011, y-.012, ball_radius*.48, dim(ball_core, visibility))
                process.stdin.write(picture.tobytes())
            process.stdin.close()
            if process.wait():
                raise BrokenPipeError()
        except BrokenPipeError:
            process.wait()
            errors.seek(0)
            raise RuntimeError('Не удалось сохранить видео с шариком: '+errors.read().decode(errors='replace')) from None
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            if not process.stdin.closed:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
    return {'seed': str(seed), 'ring_direction': direction}
