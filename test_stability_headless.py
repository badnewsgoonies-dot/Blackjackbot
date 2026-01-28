"""Headless stability analysis on timing_frames.

Runs the detector on saved frames and reports signature stability.
No display required - pure console output.
"""

import cv2
import json
from pathlib import Path
from screen_capture import GOP3Detector
from config_loader import load_config


def make_signature(state):
    """Create stability signature: (phase, button_mask, player_total)."""
    phase = state.get('phase', 'unknown')
    buttons = state.get('buttons', {})
    btn_mask = tuple(sorted(buttons.keys()))
    player_total = state.get('player_total')
    return (phase, btn_mask, player_total)


def sig_to_str(sig):
    """Convert signature to compact string like 'player_turn|0b1111|17'."""
    if not sig:
        return 'None'
    phase = sig[0] if sig[0] else '?'
    btn_order = ['hit_bet', 'stand', 'double', 'split']
    mask = 0
    if sig[1]:
        for i, btn in enumerate(btn_order):
            if btn in sig[1]:
                mask |= (1 << i)
    player = sig[2] if sig[2] is not None else '?'
    return f'{phase}|0b{mask:04b}|{player}'


def main():
    frames_dir = Path('timing_frames')
    frames = sorted(frames_dir.glob('frame_*.png'))
    
    if not frames:
        print("No frames found in timing_frames/")
        return
    
    print(f"Found {len(frames)} frames")
    print("Loading detector...")
    
    detector = GOP3Detector(load_config())
    
    print()
    print("Frame Stability Analysis")
    print("=" * 70)

    last_sig = None
    changes = []
    stable_runs = []
    current_run = 0
    all_results = []

    for i, frame_path in enumerate(frames):
        screen = cv2.imread(str(frame_path))
        if screen is None:
            print(f"{i:3}: FAILED TO LOAD {frame_path.name}")
            continue
            
        state = detector.detect_game_state(screen)
        sig = make_signature(state)
        sig_str = sig_to_str(sig)
        
        all_results.append({
            'frame': i,
            'file': frame_path.name,
            'signature': sig_str,
            'state': {
                'phase': state.get('phase'),
                'player_total': state.get('player_total'),
                'is_soft': state.get('is_soft'),
                'dealer_total': state.get('dealer_total'),
                'buttons': list(state.get('buttons', {}).keys()),
            }
        })
        
        if last_sig is None:
            print(f"{i:3}: {sig_str} (initial)")
        elif sig != last_sig:
            # Identify what changed
            change_parts = []
            if sig[0] != last_sig[0]:
                change_parts.append(f"phase:{last_sig[0]}->{sig[0]}")
            if sig[1] != last_sig[1]:
                old_btns = set(last_sig[1]) if last_sig[1] else set()
                new_btns = set(sig[1]) if sig[1] else set()
                added = new_btns - old_btns
                removed = old_btns - new_btns
                if added:
                    change_parts.append(f"+btns:{','.join(added)}")
                if removed:
                    change_parts.append(f"-btns:{','.join(removed)}")
            if sig[2] != last_sig[2]:
                change_parts.append(f"player:{last_sig[2]}->{sig[2]}")
            
            changes.append((i, change_parts))
            if current_run > 0:
                stable_runs.append(current_run)
            current_run = 0
            print(f"{i:3}: {sig_str} <- CHANGE: {' | '.join(change_parts)}")
        else:
            current_run += 1
        
        last_sig = sig

    if current_run > 0:
        stable_runs.append(current_run)

    print()
    print("=" * 70)
    print(f"Total frames analyzed: {len(all_results)}")
    print(f"Total signature changes: {len(changes)}")
    print(f"Stable runs (consecutive identical frames): {stable_runs}")
    if stable_runs:
        print(f"Avg stable run length: {sum(stable_runs)/len(stable_runs):.1f} frames")
        print(f"Max stable run: {max(stable_runs)} frames")
        print(f"Min stable run: {min(stable_runs)} frames")

    # Breakdown of change types
    phase_changes = sum(1 for _, parts in changes if any('phase:' in p for p in parts))
    button_changes = sum(1 for _, parts in changes if any('btns:' in p for p in parts))
    player_changes = sum(1 for _, parts in changes if any('player:' in p for p in parts))
    
    print()
    print("Change breakdown:")
    print(f"  Phase changes: {phase_changes}")
    print(f"  Button changes: {button_changes}")
    print(f"  Player total changes: {player_changes}")
    
    # Identify the primary instability source
    print()
    if button_changes > player_changes and button_changes > phase_changes:
        print(">>> PRIMARY INSTABILITY: BUTTONS")
        print("    Recommendation: Check HSV thresholds for button color validation")
    elif player_changes > button_changes and player_changes > phase_changes:
        print(">>> PRIMARY INSTABILITY: PLAYER TOTAL (OCR)")
        print("    Recommendation: Check blue circle detection and OCR preprocessing")
    elif phase_changes > 0:
        print(">>> PRIMARY INSTABILITY: PHASE")
        print("    Recommendation: Phase is derived from buttons/totals - fix those first")
    else:
        print(">>> DETECTION APPEARS STABLE")
    
    # Save detailed results
    output_file = Path('diagnostics/headless_stability_report.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump({
            'summary': {
                'total_frames': len(all_results),
                'total_changes': len(changes),
                'phase_changes': phase_changes,
                'button_changes': button_changes,
                'player_changes': player_changes,
                'stable_runs': stable_runs,
            },
            'changes': [{'frame': c[0], 'what': c[1]} for c in changes],
            'frames': all_results,
        }, f, indent=2)
    print(f"\nDetailed report saved to: {output_file}")


if __name__ == '__main__':
    main()
