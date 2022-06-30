from pyrogram import filters


def step_filter(data):
    async def check_step(flt, __, msg):
        return flt.data == msg.step

    return filters.create(check_step, data=data)
