class Base:
    async def run(self):
        return "async"


METHOD = "Base.run"


def observed_types():
    return [Base]
