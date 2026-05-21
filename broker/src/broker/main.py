import zmq


def main() -> None:
    with zmq.Context() as ctx:
        with (
            ctx.socket(zmq.XSUB) as frontend,
            ctx.socket(zmq.XPUB) as backend,
        ):
            frontend.bind("tcp://*:5559")
            backend.bind("tcp://*:5560")
            zmq.proxy(frontend, backend)


if __name__ == "__main__":
    main()
