LIBRARY()



SRCS(
    http_parser.cpp
)

PEERDIR(
    library/http/io
    library/blockcodecs
)

END()

RECURSE_FOR_TESTS(ut)
