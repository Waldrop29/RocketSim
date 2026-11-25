import pygame
import sys
import time
import math
import random  

# --- CORE INITIALIZATION ---
pygame.init()
pygame.font.init()  # Initialize font system for the HUD text
pygame.joystick.init()

hotas = None
if pygame.joystick.get_count() > 0:
    hotas = pygame.joystick.Joystick(0)
    hotas.init()
    print("HOTAS link established.")
else:
    print("No HOTAS detected. Keyboard docking controls enabled.")

# --- WINDOW CONFIGURATION ---
WIDTH, HEIGHT = 1000, 800  
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Vanguard Mk-1 Flight Systems Interface")

# Docking HUD typography
HUDFont = pygame.font.SysFont("Courier", 72, bold=True)
HelpFont = pygame.font.SysFont("Courier", 12, bold=True)
CaptureSubFont = pygame.font.SysFont("Courier", 22, bold=True)

# --- COLOR SCHEMES ---
SPACE_BLACK = (5, 5, 10)
HULL_GREEN  = (0, 255, 100)
HUD_DARK    = (0, 50, 20)
WHITE       = (255, 255, 255)
EXHAUST_RED = (255, 50, 50)
TARGET_GOLD = (230, 190, 30)
PANEL_GREY  = (35, 38, 42)

# --- OPTIONAL HOTAS MAPPING ---
ROLL_AXIS       = 0       
THROTTLE_AXIS   = 2   
LEFT_BRAKE_AXIS = 3  
RIGHT_BRAKE_AXIS = 4 
YAW_AXIS        = 5        
TOGGLE_BUTTON   = 0   

# --- SIMULATION STATE & KINEMATICS ---
ship_x = random.randint(150, WIDTH - 150)
ship_y = random.randint(150, HEIGHT - 150)
ship_roll = 0.0   

vel_x = 0.0
vel_y = 0.0

# Mechanical state tracking
probe_extended = False
probe_current_length = 0.0
button_state_lock = False

# --- NEW: DOCKING MISSION STATES ---
# Valid states: "FLYING", "DOCKED", "RETRACTING", "CAPTURED"
mission_state = "FLYING" 

# Aerospace Physics Constants
THRUST_MODIFIER = 400.0   
LATERAL_MODIFIER = 300.0  
MOMENTUM_RETENTION = 0.985 

# LOCKED DOCKING PORT COORDINATES
target_x = WIDTH // 2
target_y = HEIGHT // 2

clock = pygame.time.Clock()
last_frame_time = time.time()

try:
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                pygame.quit()
                sys.exit()
        
        # Calculate Delta Time (dt)
        current_frame_time = time.time()
        dt = current_frame_time - last_frame_time
        last_frame_time = current_frame_time
        
        # Keyboard: W/S translate forward/back, A/D strafe, Q/E yaw, Space probe.
        if mission_state != "CAPTURED":
            if hotas is not None:
                roll_input = hotas.get_axis(ROLL_AXIS)
                raw_throttle = hotas.get_axis(THROTTLE_AXIS)
                yaw_input = hotas.get_axis(YAW_AXIS)
                left_toe = (hotas.get_axis(LEFT_BRAKE_AXIS) + 1.0) / 2.0
                right_toe = (hotas.get_axis(RIGHT_BRAKE_AXIS) + 1.0) / 2.0
                trigger_pressed = hotas.get_button(TOGGLE_BUTTON)
            else:
                keys = pygame.key.get_pressed()
                roll_input = float(keys[pygame.K_e]) - float(keys[pygame.K_q])
                raw_throttle = float(keys[pygame.K_s]) - float(keys[pygame.K_w])
                yaw_input = 0.0
                left_toe = float(keys[pygame.K_a])
                right_toe = float(keys[pygame.K_d])
                trigger_pressed = bool(keys[pygame.K_SPACE])
        else:
            # Freeze controls after capture.
            roll_input = raw_throttle = yaw_input = left_toe = right_toe = 0.0
            trigger_pressed = False
        
        # 2. PROBE TOGGLE LOGIC
        if trigger_pressed and not button_state_lock:
            if mission_state == "DOCKED":
                mission_state = "RETRACTING"
                probe_extended = False
            elif mission_state == "FLYING":
                probe_extended = not probe_extended
            button_state_lock = True
        elif not trigger_pressed:
            button_state_lock = False

        thrust_level = (1.0 - raw_throttle) / 2.0
        
        # 3. MISSION SEQUENCE STATE MACHINE
        if mission_state == "FLYING":
            # Normal Flight Controls active
            ship_roll += (roll_input * 100.0) * dt
            ship_roll %= 360.0
            
            forward_accel = (thrust_level - 0.5) * 2.0 * THRUST_MODIFIER
            strafe_accel = (yaw_input + right_toe - left_toe) * LATERAL_MODIFIER
            heading_radians = math.radians(ship_roll)
            forward_x = math.sin(heading_radians)
            forward_y = -math.cos(heading_radians)
            right_x = math.cos(heading_radians)
            right_y = math.sin(heading_radians)
            vel_x += (forward_x * forward_accel + right_x * strafe_accel) * dt
            vel_y += (forward_y * forward_accel + right_y * strafe_accel) * dt
            
            ship_x += vel_x * dt
            ship_y += vel_y * dt
            retention = MOMENTUM_RETENTION ** (dt * 60.0)
            vel_x *= retention
            vel_y *= retention

        elif mission_state == "DOCKED":
            # IMMOBILIZED: Magnet holds the ship rigid in space.
            vel_x = 0.0
            vel_y = 0.0

        elif mission_state == "RETRACTING":
            # AUTOMATED DRAW: Ship crawls toward target center as probe shrinks
            dx = target_x - ship_x
            dy = target_y - ship_y
            distance_to_core = math.sqrt(dx**2 + dy**2)
            
            if distance_to_core > 2.0:
                # Smoothly glide ship to center coordinates
                ship_x += (dx / distance_to_core) * 80.0 * dt
                ship_y += (dy / distance_to_core) * 80.0 * dt
            else:
                ship_x, ship_y = target_x, target_y
                mission_state = "CAPTURED"

        # Probe mechanical animation interpolation
        if probe_extended and probe_current_length < 35.0:
            probe_current_length += 120.0 * dt
        elif not probe_extended and probe_current_length > 0.0:
            probe_current_length -= 120.0 * dt

        # Bound constraints (Active only during manual flight)
        if mission_state == "FLYING":
            ship_x = max(120, min(WIDTH - 120, ship_x))
            ship_y = max(120, min(HEIGHT - 120, ship_y))

        # --- GRAPHICS PIPELINE ---
        screen.fill(SPACE_BLACK) 
        
        # LAYER 1: Target Port
        pygame.draw.circle(screen, TARGET_GOLD, (target_x, target_y), 90, 1)
        pygame.draw.line(screen, TARGET_GOLD, (target_x - 130, target_y), (target_x + 130, target_y), 1)
        pygame.draw.line(screen, TARGET_GOLD, (target_x, target_y - 130), (target_x, target_y + 130), 1)
        pygame.draw.circle(screen, EXHAUST_RED, (target_x, target_y), 4, 0)
        
        # Vector Trigonometry
        rad_calc = math.radians(ship_roll)
        cos_val = math.cos(rad_calc)
        sin_val = math.sin(rad_calc)
        
        # LAYER 2: Vessel Structural Elements
        node_nose   = (ship_x + (0 * cos_val - (-35) * sin_val), ship_y + (0 * sin_val + (-35) * cos_val))
        node_port   = (ship_x + (-25 * cos_val - 25 * sin_val), ship_y + (-25 * sin_val + 25 * cos_val))
        node_star   = (ship_x + (25 * cos_val - 25 * sin_val), ship_y + (25 * sin_val + 25 * cos_val))
        
        # Projecting structural probe mechanics
        node_tip = node_nose
        if probe_current_length > 0 or mission_state == "RETRACTING":
            node_tip = (ship_x + (0 * cos_val - (-35 - probe_current_length) * sin_val), ship_y + (0 * sin_val + (-35 - probe_current_length) * cos_val))
            pygame.draw.line(screen, WHITE, node_nose, node_tip, 3)
            # The magnetic indicator tip
            pygame.draw.circle(screen, TARGET_GOLD, (int(node_tip[0]), int(node_tip[1])), 5)

        # HIT DETECTION LOGIC: Scan contact when probe is out
        if mission_state == "FLYING" and probe_current_length >= 30.0:
            distance_tip_to_target = math.sqrt((node_tip[0] - target_x)**2 + (node_tip[1] - target_y)**2)
            if distance_tip_to_target < 8.0:  # Contact criteria met!
                mission_state = "DOCKED"

        pygame.draw.polygon(screen, HULL_GREEN, [node_nose, node_port, node_star], 2)
        
        # Render main thruster exhaust plume
        if mission_state == "FLYING" and thrust_level > 0.52:
            flame_scale = int(50 * (thrust_level - 0.5) * 2)
            node_trail = (ship_x + (0 * cos_val - (25 + flame_scale) * sin_val), ship_y + (0 * sin_val + (25 + flame_scale) * cos_val))
            pygame.draw.line(screen, EXHAUST_RED, ((node_port[0] + node_star[0]) / 2, (node_port[1] + node_star[1]) / 2), node_trail, 4)

        # LAYER 3: Interactive Cockpit Shield
        pygame.draw.polygon(screen, PANEL_GREY, [(0, HEIGHT), (220, HEIGHT), (170, HEIGHT-130), (0, HEIGHT-160)])
        pygame.draw.polygon(screen, PANEL_GREY, [(WIDTH, HEIGHT), (WIDTH-220, HEIGHT), (WIDTH-170, HEIGHT-130), (WIDTH, HEIGHT-160)])
        pygame.draw.rect(screen, PANEL_GREY, (220, HEIGHT-45, WIDTH-440, 45))
        
        pygame.draw.line(screen, PANEL_GREY, (0, 0), (170, HEIGHT-130), 10)
        pygame.draw.line(screen, PANEL_GREY, (WIDTH, 0), (WIDTH-170, HEIGHT-130), 10)
        pygame.draw.line(screen, PANEL_GREY, (170, HEIGHT-130), (220, HEIGHT), 10)
        pygame.draw.line(screen, PANEL_GREY, (WIDTH-170, HEIGHT-130), (WIDTH-220, HEIGHT), 10)
        
        pygame.draw.rect(screen, HUD_DARK, (40, HEIGHT-115, 90, 40))
        
        # Console indicator color mapping
        if mission_state == "FLYING":
            indicator_color = HULL_GREEN if probe_extended else EXHAUST_RED
        elif mission_state == "DOCKED":
            indicator_color = TARGET_GOLD
        else:
            indicator_color = WHITE
            
        pygame.draw.circle(screen, indicator_color, (85, HEIGHT-95), 7)
        controls_surface = HelpFont.render(
            "W/S TRANSLATE  A/D STRAFE  Q/E YAW  SPACE PROBE",
            True,
            WHITE,
        )
        screen.blit(controls_surface, controls_surface.get_rect(center=(WIDTH // 2, HEIGHT - 23)))
        
        # -------------------------------------------------------------------
        # LAYER 4: HEAVY HUD ALERT OVERLAY (Renders "CAPTURE" Text)
        # -------------------------------------------------------------------
        if mission_state in ("DOCKED", "RETRACTING", "CAPTURED"):
            text_surface = HUDFont.render("CAPTURE", True, HULL_GREEN)
            text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 3))
            screen.blit(text_surface, text_rect)
        if mission_state in ("RETRACTING", "CAPTURED"):
            subtitle = CaptureSubFont.render(
                "Houston, we have hard dock.", True, WHITE
            )
            subtitle_rect = subtitle.get_rect(
                center=(WIDTH // 2, HEIGHT // 3 + 62)
            )
            screen.blit(subtitle, subtitle_rect)
        
        pygame.display.flip()
        clock.tick(60)

except KeyboardInterrupt:
    pygame.quit()
    print("\nSim closed cleanly.")