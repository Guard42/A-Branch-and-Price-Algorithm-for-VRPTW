from branchBound import BranchAndBound
from columnGen import ColumnGeneration
from paramsVRP import ParamsVRP
from route import Route
import time
import matplotlib.pyplot as plt
import numpy as np
import os
from solVisualization import solVis


def main(datasetPath = "F:/absolutePythonProject/universalPythonProject/BP-VRPTW/dataset/R101.txt", SHOWFIG = False):
    # 初始化分支定界算法
    bp = BranchAndBound()

    # 初始化问题实例
    user_param = ParamsVRP()
    user_param.init_params(datasetPath)
    dataset_name = user_param.datasetName

    # 初始化初始路径和最佳路径列表
    init_routes = []
    for i in range(user_param.nbclients - 2):
        route_cost = user_param.dist[0][i + 1] + user_param.dist[i + 1][user_param.nbclients - 1]
        route = Route(path=[0, i + 1, user_param.nbclients - 1], cost=route_cost, Q=1.0)
        init_routes.append(route)
    best_routes = []

    # 开始计时
    start_time = time.time()

    # 执行分支定界算法
    bp.bb_node(user_param, init_routes, None, best_routes, 0)

    # 结束计时
    end_time = time.time()
    sol_time = end_time - start_time

    # 计算最佳路径的成本
    opt_cost = 0
    print("\nSolution >>>")
    for route in best_routes:
        print(route.get_path())
        opt_cost += route.get_cost()

    print(f"\nBest Cost = {opt_cost}")
    print(f"Total Time = {sol_time:.2f} seconds")

    # 可视化解
    solVis(user_param, best_routes, sol_time, opt_cost, dataset_name, SHOWFIG)


def BatchMain(folder_path="F:/absolutePythonProject/universalPythonProject/BP-VRPTW/dataset", banned_datasets=("c110_1","c101")):

    datasetBatch = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.txt')]

    # 删除不想要的数据集
    datasetBan = [os.path.join(folder_path, f"{ds}.txt") for ds in banned_datasets]
    datasetBatch = [ds for ds in datasetBatch if ds not in datasetBan]

    # 对每个数据集调用main函数
    for dataset in datasetBatch:
        print(f"Processing dataset: {dataset}")
        main(dataset)

if __name__ == "__main__":

    # 单数据集处理
    main(datasetPath="F:/absolutePythonProject/universalPythonProject/BP-VRPTW/dataset/R101.txt", SHOWFIG=True)

    # 批量处理数据集
    #BatchMain(folder_path="F:/absolutePythonProject/universalPythonProject/BP-VRPTW/dataset", banned_datasets=["c110_1", "c101"])


