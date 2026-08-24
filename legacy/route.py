import copy

class Route:
    def __init__(self, path=None, cost=0.0, Q=0.0):
        """
        初始化 Route 类。

        :param path: 路径列表，默认为 None，表示空路径
        :param cost: 路径成本，默认为 0.0
        :param Q: 路径的其他资源（如流量等），默认为 0.0
        """
        self.path = path if path is not None else []
        self.cost = cost
        self.Q = Q

    def clone(self):
        """
        深拷贝当前路径对象。
        """
        return copy.deepcopy(self)

    def remove_city(self, city):
        """
        从路径中移除指定城市。

        :param city: 要移除的城市编号
        """
        if city in self.path:
            self.path.remove(city)

    def add_city(self, city, after_city=None):
        """
        向路径中添加城市。

        :param city: 要添加的城市编号
        :param after_city: 在哪个城市之后添加（可选）
        """
        if after_city is None:
            self.path.append(city)
        else:
            index = self.path.index(after_city)
            self.path.insert(index + 1, city)

    def set_cost(self, cost):
        """
        设置路径成本。

        :param cost: 新的成本值
        """
        self.cost = cost

    def get_cost(self):
        """
        获取路径成本。
        """
        return self.cost

    def set_Q(self, Q):
        """
        设置路径的其他资源（如流量等）。

        :param Q: 新的资源值
        """
        self.Q = Q

    def get_Q(self):
        """
        获取路径的其他资源（如流量等）。
        """
        return self.Q

    def get_path(self):
        """
        获取路径列表。
        """
        return self.path

    def switch_path(self):
        """
        反转路径。
        """
        self.path = self.path[::-1]

    def __str__(self):
        """
        返回路径的字符串表示形式。
        """
        return f"Route(cost={self.cost}, Q={self.Q}, path={self.path})"

    def __repr__(self):
        """
        返回路径的简短字符串表示形式。
        """
        return self.__str__()