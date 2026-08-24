import matplotlib
from matplotlib import pyplot as plt
from route import Route
from paramsVRP import ParamsVRP

matplotlib.use('TkAgg')  # 或者尝试 'Agg'

def solVis(user_param, routes, sol_time, opt_cost, dataset_name, POPOUT=False):
    """
    可视化车辆路径问题的解。
    """
    # 获取客户位置
    depot_x, depot_y = user_param.posx[0], user_param.posy[0]
    customer_x = user_param.posx[1:-1]
    customer_y = user_param.posy[1:-1]

    # 创建图形
    plt.figure(figsize=(10, 8))
    plt.title(f"B&P Solution for VRPTW on dataset {dataset_name}", fontsize=16)

    # 绘制仓库
    plt.scatter(depot_x, depot_y, color="black", s=100, label="Depot", zorder=5)
    plt.text(depot_x, depot_y, "Depot", fontsize=12, ha="right", va="bottom", color="black")

    # 绘制客户点
    plt.scatter(customer_x, customer_y, color="gray", s=50, label="Customers", zorder=5)
    for i in range(len(customer_x)):
        plt.text(customer_x[i], customer_y[i], f"{i + 1}", fontsize=10, ha="right", va="bottom", color="gray")

    # 绘制路径
    cmap = plt.cm.tab20  # 使用学术期刊推荐的色盘
    for i, route in enumerate(routes):
        path = route.get_path()
        route_x = [user_param.posx[j] for j in path]
        route_y = [user_param.posy[j] for j in path]
        color = cmap(i % cmap.N)  # 循环使用色盘颜色
        plt.plot(route_x, route_y, color=color, linewidth=2, label=f"Route {i + 1}", zorder=1)
        for j in range(len(path) - 1):
            start_x, start_y = route_x[j], route_y[j]
            end_x, end_y = route_x[j + 1], route_y[j + 1]
            mid_x = (start_x + end_x) / 2
            mid_y = (start_y + end_y) / 2

            # 计算箭头的方向
            dx = end_x - start_x
            dy = end_y - start_y

            # 添加箭头
            plt.annotate("", xy=(mid_x, mid_y), xytext=(start_x, start_y),
                         arrowprops=dict(arrowstyle="->", color=color, lw=1.5))


    # 设置图例
    plt.legend(loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.xlabel("X Coordinate", fontsize=14)
    plt.ylabel("Y Coordinate", fontsize=14)
    plt.tight_layout()

    # 在图例的正下方（右下角）添加解的信息
    info_text = (
        f"Optimal Cost: {opt_cost:.2f}\n"
        f"Total Time: {sol_time:.2f} seconds\n"
        #f"Routes: {routes.__str__()}"
    )
    plt.text(0.95, 0.1, info_text, fontsize=12, ha="left", va="top", transform=plt.gca().transAxes,
             bbox=dict(facecolor="white", edgecolor="black", boxstyle="round,pad=0.5"))

    # 显示图形
    filename = f"F:\\absolutePythonProject\\universalPythonProject\\BP-VRPTW\\fig\\VRPTW_B&P_Sol_Dataset{dataset_name}.svg"
    plt.savefig(filename)
    if POPOUT:
        plt.show()
        plt.close()
    if not POPOUT:
        plt.close()

