import sys
import subprocess

BOTS = {
    "1": ("Indian Equities", "bots.run_india_stocks"),
    "2": ("Cryptocurrency", "bots.run_crypto"),
    "3": ("Forex (INR Pairs)", "bots.run_forex"),
    "4": ("Foreign Equities (US)", "bots.run_foreign_stocks"),
}

def execute_module(module_name: str):
    print(f"\n>>> Running module: {module_name} <<<\n")
    try:
        subprocess.run([sys.executable, "-m", module_name], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Bot exited with error code {e.returncode}")
    except KeyboardInterrupt:
        print("\n[INFO] Bot execution halted by user.")

def main():
    while True:
        print("\n" + "=" * 50)
        print("       ALGORITHMIC TRADING SUITE - DASHBOARD")
        print("=" * 50)
        for key, (label, _) in BOTS.items():
            print(f" [{key}] Launch {label} Bot")
        print(" [5] Run All 4 Bots Sequentially")
        print(" [0] Exit")
        print("=" * 50)

        choice = input("Select an option (0-5): ").strip()

        if choice in BOTS:
            execute_module(BOTS[choice][1])
        elif choice == "5":
            for _, (label, module) in BOTS.items():
                execute_module(module)
        elif choice == "0":
            print("\nExiting dashboard.")
            break
        else:
            print("\nInvalid choice. Please enter a number between 0 and 5.")

if __name__ == "__main__":
    main()