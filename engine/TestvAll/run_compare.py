import json
import os
import sys
import io
from contextlib import redirect_stdout

# Ensure we can import engine and config from the parent directory
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import engine
import config

# Patch Player.build to avoid rebuilding the same bot path multiple times
original_build = engine.Player.build
built_paths = set()

def patched_build(self):
    # Always load commands.json as the original build does
    try:
        if self.commands is None:
            with open(self.path + '/commands.json', 'r') as json_file:
                commands = json.load(json_file)
            if ('build' in commands and 'run' in commands and
                    isinstance(commands['build'], list) and
                    isinstance(commands['run'], list)):
                self.commands = commands
            else:
                print(self.name, 'commands.json missing command')
    except Exception as e:
        print(f"Error loading commands for {self.name}: {e}")

    # Only run the actual build command if we haven't built this path yet
    if self.path not in built_paths:
        if self.commands is not None and len(self.commands['build']) > 0:
            print(f"Building {self.name} at {self.path}...")
            # We call the original logic but without reloading commands
            # To keep it simple, we just do what original_build does for the build part
            import subprocess
            from queue import Queue
            try:
                proc = subprocess.run(self.commands['build'],
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      cwd=self.path, timeout=getattr(engine, 'BUILD_TIMEOUT', 30.0), check=False)
                self.bytes_queue.put(proc.stdout)
            except Exception as e:
                print(f"Build failed for {self.name}: {e}")
        built_paths.add(self.path)
    else:
        # print(f"Skipping build for {self.name} (already built)")
        pass

# Apply the patch
engine.Player.build = patched_build

def run_match(name1, path1, name2, path2):
    print(f"Running {name1} vs {name2}...")
    
    # Configure the engine to match config.py and specific match players
    # We use getattr to get values from config, or fallback to reasonable defaults
    conf_vars = {
        'PLAYER_1_NAME': name1,
        'PLAYER_1_PATH': path1,
        'PLAYER_2_NAME': name2,
        'PLAYER_2_PATH': path2,
        'GAME_LOG_FILENAME': f'gamelog_{name1}_vs_{name2}',
        'STARTING_GAME_CLOCK': getattr(config, 'STARTING_GAME_CLOCK', 30.0),
        'BUILD_TIMEOUT': getattr(config, 'BUILD_TIMEOUT', 10.0), 
        'CONNECT_TIMEOUT': getattr(config, 'CONNECT_TIMEOUT', 10.0),
        'NUM_ROUNDS': getattr(config, 'NUM_ROUNDS', 1000),
        'STARTING_STACK': getattr(config, 'STARTING_STACK', 400),
        'BIG_BLIND': getattr(config, 'BIG_BLIND', 2),
        'SMALL_BLIND': getattr(config, 'SMALL_BLIND', 1),
        'ENFORCE_GAME_CLOCK': getattr(config, 'ENFORCE_GAME_CLOCK', True),
        'PLAYER_LOG_SIZE_LIMIT': getattr(config, 'PLAYER_LOG_SIZE_LIMIT', 524288)
    }
    
    # Update both engine and config modules
    for var, val in conf_vars.items():
        setattr(engine, var, val)
        setattr(config, var, val)

    # Change directory to base_dir so engine and bots find their files
    old_cwd = os.getcwd()
    os.chdir(base_dir)
    
    output_capture = io.StringIO()
    success = False
    br1, br2 = 0, 0
    
    try:
        # We redirect stdout to keep the console clean, but capture it for debugging if needed
        with redirect_stdout(output_capture):
            game = engine.Game()
            game.run()
        success = True
    except Exception as e:
        print(f"Error running match {name1} vs {name2}: {e}")
        print(output_capture.getvalue())
    finally:
        os.chdir(old_cwd)

    if success:
        log_path = os.path.join(base_dir, f"{conf_vars['GAME_LOG_FILENAME']}.txt")
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                lines = f.readlines()
                # Search for the final bankroll line
                for line in reversed(lines):
                    if line.startswith('Final'):
                        try:
                            # Format: Final, Name1 (br1), Name2 (br2)
                            parts = line.strip().split(', ')
                            def parse_br(p): return int(p.split('(')[1].split(')')[0])
                            
                            # engine.py swaps players after each round. 
                            # After an even number of rounds, they are in original order [P1, P2].
                            # After an odd number of rounds, they are in swapped order [P2, P1].
                            num_rounds = conf_vars['NUM_ROUNDS']
                            if num_rounds % 2 == 0:
                                # Order is P1, P2
                                br1 = parse_br(parts[1])
                                br2 = parse_br(parts[2])
                            else:
                                # Order is P2, P1
                                br2 = parse_br(parts[1])
                                br1 = parse_br(parts[2])
                            break
                        except Exception as e:
                            print(f"Error parsing final line: {e}")
            
            # Cleanup engine logs
            try:
                os.remove(log_path)
                p1_log = os.path.join(base_dir, f"{name1}.txt")
                p2_log = os.path.join(base_dir, f"{name2}.txt")
                if os.path.exists(p1_log): os.remove(p1_log)
                if os.path.exists(p2_log): os.remove(p2_log)
            except Exception as e:
                pass
        else:
            print(f"Log file not found for {name1} vs {name2}")
            # print(output_capture.getvalue())
    
    return br1, br2

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bots_json_path = os.path.join(script_dir, 'bots.json')
    
    if not os.path.exists(bots_json_path):
        print(f"Error: {bots_json_path} not found.")
        return

    with open(bots_json_path, 'r') as f:
        bots = json.load(f)
    
    bot_names = list(bots.keys())
    results = {}

    # Run matches between all pairs
    for i in range(len(bot_names)):
        for j in range(i + 1, len(bot_names)):
            name1 = bot_names[i]
            path1 = bots[name1]
            name2 = bot_names[j]
            path2 = bots[name2]
            
            br1, br2 = run_match(name1, path1, name2, path2)
            match_key = f"{name1}_vs_{name2}"
            results[match_key] = {
                name1: br1,
                name2: br2
            }
            print(f"  Result: {name1}: {br1}, {name2}: {br2}")

    results_path = os.path.join(script_dir, 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=4)
    print(f"Comparison complete. Results saved to {results_path}")

if __name__ == "__main__":
    main()
