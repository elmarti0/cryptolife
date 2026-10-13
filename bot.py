"""CryptoLife: paper trading only, standard library, Python 3.10+."""
import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import math
import os
from pathlib import Path
import random
import time
import urllib.request


def positive(value):
    if not math.isfinite(value) or value <= 0:
        raise ValueError("La valeur doit être finie et positive.")
    return value


@dataclass
class Wallet:
    initial: float = 100.0
    cash: float = 100.0
    units: float = 0.0
    price: float = 0.0
    withdrawn: float = 0.0
    status: str = "ALIVE"
    source: str = "new"
    high_water: float = 100.0
    last_time: float = 0.0
    history: list = field(default_factory=list)
    events: list = field(default_factory=list)
    fee: float = 0.006
    slippage: float = 0.001
    death_floor: float = 5.0
    max_drawdown: float = 0.20

    def equity(self):
        return self.cash + self.units * self.price

    def liquidation_value(self):
        return self.cash + self.units * self.price * (1-self.slippage)*(1-self.fee)

    def event(self, kind, reason, **details):
        self.events.append(dict(time=self.last_time, kind=kind, reason=reason, **details))

    def buy(self):
        # At most 25% of current equity; one long-only position, no borrowing.
        budget = min(self.cash, self.equity()*0.25)
        if budget < 5 or self.units > 0 or self.status != "ALIVE":
            return
        execution = self.price * (1+self.slippage)
        self.units = budget / (execution*(1+self.fee))
        self.cash -= budget
        self.event("BUY", "Moyenne courte supérieure à la moyenne longue", budget=budget)

    def sell(self, reason):
        if self.units <= 0:
            return
        proceeds = self.units*self.price*(1-self.slippage)*(1-self.fee)
        self.cash += proceeds
        self.units = 0.0
        self.event("SELL", reason, proceeds=proceeds)

    def risk_check(self):
        if self.status == "DEAD":
            return
        value = self.liquidation_value()
        if value <= self.death_floor:
            self.sell("Capital sous le seuil de survie")
            self.status = "DEAD"
            self.event("DEAD", "Arrêt définitif de ce portefeuille")
            return
        self.high_water = max(self.high_water, value)
        if value <= self.high_water*(1-self.max_drawdown):
            self.sell("Limite de perte depuis le sommet atteinte")
            self.status = "PAUSED"
            self.event("PAUSED", "Arrêt de protection")

    def tick(self, price, stamp):
        positive(price)
        positive(stamp)
        if stamp <= self.last_time:
            return False
        self.price, self.last_time = price, stamp
        self.history = (self.history+[price])[-30:]
        self.risk_check()
        if self.status == "ALIVE" and len(self.history) == 30:
            fast = sum(self.history[-7:])/7
            slow = sum(self.history)/30
            if fast > slow*1.002:
                self.buy()
            elif fast < slow*0.998:
                self.sell("Tendance baissière")
            self.risk_check()
        return True

    def withdraw(self, amount):
        positive(amount)
        if self.price <= 0:
            raise ValueError("Il faut un prix avant de simuler un retrait.")
        # Net cumulative profit: subtract prior withdrawals and estimated liquidation costs.
        reserve = max(self.initial, self.death_floor+0.01)
        available = max(0.0, self.liquidation_value()-reserve)
        if amount > available+1e-9:
            raise ValueError(f"Bénéfice retirable insuffisant : {available:.2f} USD.")
        if amount > self.cash:
            self.sell("Liquidation pour retrait demandé par le propriétaire")
        self.cash -= amount
        self.withdrawn += amount
        self.high_water = max(self.death_floor, self.high_water-amount)
        self.event("WITHDRAW_SIMULATED", "Demande du propriétaire, aucun transfert réel", amount=amount)
        self.risk_check()


@contextmanager
def locked(path):
    lock = Path(str(path)+".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Portefeuille occupé. Arrête le bot avant une autre commande.") from None
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def save(path, wallet):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(str(path)+".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        json.dump(asdict(wallet), output, ensure_ascii=False, indent=2, allow_nan=False)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def load(path):
    if not path.exists():
        raise ValueError("Crée le portefeuille avec la commande init.")
    return Wallet(**json.loads(path.read_text(encoding="utf-8")))


def quote():
    request = urllib.request.Request(
        "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
        headers={"User-Agent": "CryptoLife-Paper/0.1", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.load(response)
    price = positive(float(data["price"]))
    stamp = datetime.fromisoformat(data["time"].replace("Z", "+00:00")).timestamp()
    if not 0 <= time.time()-stamp <= 180:
        raise ValueError("Prix périmé ou horodatage futur : aucune transaction.")
    return price, stamp


def report(w):
    return dict(mode="PAPER_ONLY", market="BTC-USD", status=w.status,
                equity=round(w.equity(), 4), cash=round(w.cash, 4),
                btc=w.units, price=w.price, simulated_withdrawals=w.withdrawn,
                total_profit=round(w.equity()+w.withdrawn-w.initial, 4),
                samples=len(w.history), events=len(w.events))


def main():
    parser = argparse.ArgumentParser(description="CryptoLife — simulation exclusivement")
    parser.add_argument("--state", type=Path, default=Path("data/wallet.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--capital", type=float, default=100)
    sub.add_parser("status")
    sub.add_parser("events")
    sub.add_parser("pause")
    run = sub.add_parser("run")
    run.add_argument("--interval", type=int, default=60)
    demo = sub.add_parser("demo")
    demo.add_argument("--steps", type=int, default=180)
    withdraw = sub.add_parser("withdraw")
    withdraw.add_argument("amount", type=float)
    args = parser.parse_args()
    try:
        with locked(args.state):
            if args.command == "init":
                if args.state.exists():
                    raise ValueError("Portefeuille existant : initialise un autre fichier explicitement.")
                capital = positive(args.capital)
                if capital <= 5:
                    raise ValueError("Le capital initial doit dépasser le seuil de survie de 5 USD.")
                w = Wallet(initial=capital, cash=capital, high_water=capital)
            else:
                w = load(args.state)
            if args.command == "run":
                if w.source == "synthetic":
                    raise ValueError("Les prix synthétiques ne peuvent pas être mélangés aux prix publics.")
                if args.interval < 60:
                    raise ValueError("Intervalle minimum : 60 secondes.")
                w.source = "coinbase"
                while w.status == "ALIVE":
                    try:
                        price, stamp = quote()
                        w.tick(price, stamp)
                        save(args.state, w)
                        print(json.dumps(report(w)), flush=True)
                    except (OSError, ValueError, KeyError, TypeError) as error:
                        print(f"Données indisponibles, aucune transaction : {error}", flush=True)
                    time.sleep(args.interval)
            elif args.command == "demo":
                # Separate synthetic replay. Never mix historical/demo quotes into a live state.
                if w.last_time > 0:
                    raise ValueError("La démo exige un portefeuille neuf dédié.")
                if not 30 <= args.steps <= 10000:
                    raise ValueError("Nombre de pas autorisé : 30 à 10000.")
                rng = random.Random(42)
                w.source = "synthetic"
                price = 50000.0
                for i in range(args.steps):
                    price *= 1 + 0.004*math.sin(i/20) + rng.uniform(-0.008, 0.008)
                    w.tick(price, 1700000000+i*60)
            elif args.command == "withdraw":
                if time.time()-w.last_time > 180:
                    raise ValueError("Prix trop ancien : actualise via run avant un retrait.")
                w.withdraw(args.amount)
            elif args.command == "pause":
                if w.status != "DEAD":
                    w.status = "PAUSED"
                    w.event("PAUSED", "Arrêt manuel; position conservée")
            elif args.command == "events":
                print(json.dumps(w.events, ensure_ascii=False, indent=2))
                return
            save(args.state, w)
            print(json.dumps(report(w), ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        print("Bot arrêté; portefeuille enregistré au dernier cycle.")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Erreur : {error}\n")


if __name__ == "__main__":
    main()
