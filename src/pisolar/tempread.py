def read_temp_c(device_id: str) -> float:
    with open(f"/sys/bus/w1/devices/{device_id}/w1_slave") as f:
        data = f.read()
    if "YES" not in data.split("\n")[0]:
        raise IOError("CRC check failed")
    return int(data.split("t=")[-1]) / 1000.0
print(read_temp_c("28-000000788820"))