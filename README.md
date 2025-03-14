# A-Branch-and-Price-Algorithm-for-VRPTW
This Repo implements a branch-and-price algorithm for Vehicle Routing Problems with Time Windows using Python. (Gurobi license needed)
![B&P solution for VRPTW on dataset R101](https://github.com/Guard42/A-Branch-and-Price-Algorithm-for-VRPTW/blob/main/fig/VRPTW_B&P_Sol_DatasetR101.png)

# Contact
If you have any questions regarding this repository, feel free to reach out.
Author: Junwei Li([junweilee@njust.edu.cn](mailto:junweilee@njust.edu.cn))

# Updates
* March 14, 2025: Upload code and data for the B&P algorithm to solve VRPTW.

# Files
**code**: Code for a branch and price algorithm to solve VRPTW
- `branchBound.py`: Implements the Branch-and-Bound algorithm to solve Vehicle Routing Problems with Time Windows (VRPTW).
- `columnGen.py`: Contains the column generation algorithm used in the Branch-and-Bound algorithm.
- `paramsVRP.py`: Defines the parameter class for Vehicle Routing Problems (VRP), used for storing and processing parameters and data.
- `route.py`: Defines the Route class, used to represent and manipulate vehicle routes.
- `solVisualization.py`: Provides visualization functionality for displaying solutions to VRPTW.
- `SPPRC.py`: Implements the label setting and label correcting algorithm t o solve the Shortest Path Problem with Resource Constraints, which will generate routes with negative cost to improve the objective function.
- `main.py`: The main script file to run the Branch-and-Bound algorithm.

# Dataset

This repository implements a Branch-and-Price algorithm to solve the Vehicle Routing Problem with Time Windows (VRPTW). The algorithm has been benchmarked using the Solomon dataset, a widely recognized set of instances in the field of vehicle routing problems.

## Solomon Dataset

The Solomon dataset, introduced by Marius Solomon in 1987, comprises 56 instances designed to evaluate the performance of VRPTW algorithms. Each instance includes 100 customers and is categorized based on customer distribution and scheduling horizon. The dataset is divided into six distinct types: C1, C2, R1, R2, RC1, and RC2.

### Instance Categories

1. **C-Type (Clustered Customers)**
   - **C1:** Features clustered customer locations with narrow time windows and small vehicle capacities, leading to solutions with more routes and fewer customers per route.
   - **C2:** Similar to C1 but with larger time windows and vehicle capacities, resulting in fewer routes with more customers per route.

2. **R-Type (Randomly Distributed Customers)**
   - **R1:** Contains randomly distributed customers with narrow time windows and small vehicle capacities, leading to solutions with more routes and fewer customers per route.
   - **R2:** Similar to R1 but with larger time windows and vehicle capacities, resulting in fewer routes with more customers per route.

3. **RC-Type (Mixed Distribution of Customers)**
   - **RC1:** Combines both clustered and randomly distributed customers with narrow time windows and small vehicle capacities, leading to solutions with more routes and fewer customers per route.
   - **RC2:** Similar to RC1 but with larger time windows and vehicle capacities, resulting in fewer routes with more customers per route.

Each instance file is named to reflect its category and specific characteristics. For example, `c101.txt` indicates a C1-type instance, while `r201.txt` corresponds to an R2-type instance.

## Benchmark Testing


Results on several datasets are documented in the `fig` directory and the B&P algorithm is proved efficient in solving the VRPTW (in some scenarios). **DO NOTICE** that though B&P is a efficient algorithm, its solving time for large scale dataset (with 100+ client nodes) will be huge.

**PLEASE DO NOTE** that The algorithm have not been tested across all instance types (`c101.txt` to `rc208.txt`). And It is confirmed that the algorithm solving SPPRC will end up into a dead cycle when solving dataset `c104.txt`. But unfortunately this repo will not be updated regarding this issue in the near future and we welcome commits dedicated to solving this bug.

For further details on the Solomon dataset and its applications, please refer to the original publication by Marius Solomon.

# Environment Requirements
To set up the required environment, install the dependencies listed in the `requirements.txt` file:

```
pip install requirements.txt -r
```
In addition to installing all the dependencies for this program, you also need to have a Gurobi License on your computer.

# Acknowledgement
This work is largely based on the repo [dengfaheng/BPVRPTW](https://github.com/dengfaheng/BPVRPTW)

# References

- [Solomon's VRPTW Benchmark Problems](https://w.cba.neu.edu/~msolomon/problems.htm)
- [运筹优化常用模型、算法及案例实战——Python+Java实现](http://www.tup.tsinghua.edu.cn/booksCenter/book_09109001.html)
- [优化-详解资源受限的基本最短路问题(ESPPRC)-模型、复杂度证明及C++调用CPLEX代码实现](https://zhuanlan.zhihu.com/p/624558974)
- [优化 | 详解标签算法求解资源受限的基本最短路问题(ESPPRC)【续】：理论、案例及C++实现](https://zhuanlan.zhihu.com/p/627964895)
