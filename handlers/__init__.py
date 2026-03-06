from handlers import start, earn, bonus, profile, promo, withdraw, tasks, top, games, admin, botohub, duel, search, lottery

routers = [
    botohub.router,  # must be first so botohub:check is matched before other handlers
    start.router,
    earn.router,
    bonus.router,
    profile.router,
    promo.router,
    withdraw.router,
    tasks.router,
    top.router,
    games.router,
    lottery.router,
    duel.router,
    search.router,
    admin.router,
]

__all__ = ["routers"]
