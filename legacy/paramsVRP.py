import numpy as np

# this class contains the inputs and methods to read the inputs
# for the Branch and Price CVRP with TW

class ParamsVRP:
    def __init__(self, nbclients=25, capacity=0, mvehic=0, speed=1.0, service_in_tw=False):
        """
        初始化参数类，用于存储和处理车辆路径问题（VRP）的相关参数。

        :param nbclients: 客户数量（不包括起始和结束仓库）
        :param capacity: 车辆容量
        :param mvehic: 车辆数量
        :param speed: 车辆速度
        :param service_in_tw: 是否考虑服务时间在时间窗内
        """
        self.datasetName = ""
        self.verbose = False
        self.rndseed = 0
        self.nbclients = nbclients  # 客户数量
        self.capacity = capacity  # 车辆容量
        self.mvehic = mvehic  # 车辆数量
        self.speed = speed  # 车辆速度
        self.service_in_tw = service_in_tw  # 是否考虑服务时间在时间窗内

        self.verybig = 1e10  # 一个非常大的数，用于表示无穷大
        self.gap = 1e-6  # 优化过程中的容忍误差
        self.maxlength = 0.0  # 最大路径长度

        self.citieslab = None  # 城市标签
        self.posx = None  # 城市 x 坐标
        self.posy = None  # 城市 y 坐标
        self.d = None  # 城市需求
        self.a = None  # 时间窗开始时间
        self.b = None  # 时间窗结束时间
        self.s = None  # 服务时间

        self.dist_base = None  # 原始距离矩阵
        self.dist = None  # 更新后的距离矩阵
        self.ttime = None  # 行驶时间矩阵
        self.cost = None  # 成本矩阵
        self.edges = None  # 边的权重矩阵
        self.wval = None  # 辅助变量

    def init_params(self, input_path):
        try:
            with open(input_path, 'r') as file:
                lines = file.readlines()

            # 检查文件内容是否符合预期
            if len(lines) < 10:  # 至少需要 10 行数据
                raise ValueError(f"文件 {input_path} 的行数不足，无法读取所需数据。")

            # 打印文件的前几行以便调试
            '''
            print("文件内容（前 10 行）：")
            for i in range(min(10, len(lines))):
                print(f"行 {i}: {lines[i].strip()}")
            '''

            self.datasetName = lines[0].strip()
            print(f'----------[读入数据集：{self.datasetName}]----------')

            self.mvehic = int(lines[4].strip().split()[0])
            self.capacity = int(lines[4].strip().split()[1])
            self.nbclients = len(lines) - 9
            print(f'车辆数量：{self.mvehic}')
            print(f'容量：{self.capacity}')
            print(f'客户数量：{self.nbclients}')

            # 初始化其他数据结构
            self.citieslab = [None] * self.nbclients
            self.posx = np.zeros(self.nbclients)
            self.posy = np.zeros(self.nbclients)
            self.d = np.zeros(self.nbclients)
            self.a = np.zeros(self.nbclients, dtype=int)
            self.b = np.zeros(self.nbclients, dtype=int)
            self.s = np.zeros(self.nbclients, dtype=int)
            self.dist_base = np.zeros((self.nbclients, self.nbclients))
            self.dist = np.zeros((self.nbclients, self.nbclients))
            self.ttime = np.zeros((self.nbclients, self.nbclients))
            self.cost = np.zeros((self.nbclients, self.nbclients))
            self.edges = np.zeros((self.nbclients, self.nbclients))
            self.wval = np.zeros(self.nbclients)

            # 读取客户数据
            for i in range(0, self.nbclients-1):
                data = lines[9 + i].split()

                self.citieslab[i] = int(data[0])  # 客户编号
                self.posx[i] = float(data[1])  # x 坐标
                self.posy[i] = float(data[2])  # y 坐标
                self.d[i] = float(data[3])  # 需求
                self.a[i] = int(data[4])  # 时间窗开始时间
                self.b[i] = int(data[5])  # 时间窗结束时间
                self.s[i] = int(data[6])  # 服务时间
                if self.service_in_tw:
                    self.b[i] -= self.s[i]  # 如果服务时间在时间窗内，则调整时间窗结束时间
                print(f"客户 {i}: {self.citieslab[i]} {self.posx[i]} {self.posy[i]} {self.d[i]} {self.a[i]} {self.b[i]} {self.s[i]}")

            # 复制仓库信息到结束仓库
            self.citieslab[self.nbclients - 1] = self.nbclients - 1
            self.posx[self.nbclients - 1] = self.posx[0]
            self.posy[self.nbclients - 1] = self.posy[0]
            self.d[self.nbclients - 1] = 0.0
            self.a[self.nbclients - 1] = self.a[0]
            self.b[self.nbclients - 1] = self.b[0]
            self.s[self.nbclients - 1] = 0
            print(f'结束仓库{self.citieslab[self.nbclients - 1]}: {self.citieslab[self.nbclients - 1]} '
                        f'{self.posx[self.nbclients - 1]} {self.posy[self.nbclients - 1]} {self.d[self.nbclients - 1]} '
                        f'{self.a[self.nbclients - 1]} {self.b[self.nbclients - 1]} {self.s[self.nbclients - 1]}')

            # 计算距离矩阵
            for i in range(self.nbclients):
                max = 0
                for j in range(self.nbclients):
                    # truncate to get the same results as in Solomon
                    self.dist_base[i, j] = np.round(
                        10 * np.sqrt((self.posx[i] - self.posx[j]) ** 2 + (self.posy[i] - self.posy[j]) ** 2)) / 10.0
                    if max < self.dist_base[i, j]:
                        max = self.dist_base[i, j]
                self.maxlength += max

            # 设置仓库到仓库的距离为无穷大
            for i in range(self.nbclients):
                self.dist_base[i, 0] = self.verybig
                self.dist_base[self.nbclients - 1, i] = self.verybig
                self.dist_base[i, i] = self.verybig

            for i in range(self.nbclients):
                for j in range(self.nbclients):
                    self.dist[i, j] = self.dist_base[i, j]

            # 计算行驶时间矩阵
            for i in range(self.nbclients):
                for j in range(self.nbclients):
                    self.ttime[i, j] = self.dist_base[i, j] / self.speed

            # 其他边的成本在列生成中给出
            for j in range(self.nbclients):
                self.cost[0][j] = self.dist[0][j]
                self.cost[j][self.nbclients - 1] = self.dist[j][self.nbclients - 1]

            #print(f"[距离矩阵dist已初始化]\n{self.dist}")
            #print(f"[时间矩阵ttime已初始化]\n{self.ttime}")
            #print(f"[成本矩阵cost已初始化]\n{self.cost}")

            for i in range(1, self.nbclients):
                self.wval[i] = 0.0
            print(f"[辅助变量wval已初始化]\n{self.wval}")

            print(f"----------[ParamsVRP初始化已完毕]----------")


        except FileNotFoundError:
            print(f"错误：文件 {input_path} 未找到。")
        except ValueError as e:
            print(f"ValueError：{e}")
        except Exception as e:
            print(f"Error in init_params：{e}")

    def __str__(self):
        """
        打印参数信息。
        """
        return (f"ParamsVRP(\n"
                f"  nbclients={self.nbclients},\n"
                f"  capacity={self.capacity},\n"
                f"  mvehic={self.mvehic},\n"
                f"  speed={self.speed},\n"
                f"  service_in_tw={self.service_in_tw},\n"
                f"  verybig={self.verybig},\n"
                f"  gap={self.gap},\n"
                f"  maxlength={self.maxlength}\n"
                f")")