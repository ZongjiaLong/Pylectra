# import os
# os.environ["JOBLIB_TEMP_FOLDER"] = "E:/joblib_tmp"
# os.makedirs("E:/joblib_tmp", exist_ok=True)

from pylectra.run import run

# 直接传 YAML 路径
out = run("examples/single_case39.yaml")
#
# # 看输出
# print(f"仿真时长: {out.result.simulation_time:.2f} s")
# print(f"时间点数: {out.result.Time.shape[0]}")
# print(f"发电机数: {out.result.Angles.shape[1]}")
# print(f"最大角偏差: {out.result.max_angle_deviation_deg:.2f} 度")