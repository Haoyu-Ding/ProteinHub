from proteinhub.app import create_app

app = create_app()

if __name__ in {"__main__", "__mp_main__"}:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080, reload=False)
