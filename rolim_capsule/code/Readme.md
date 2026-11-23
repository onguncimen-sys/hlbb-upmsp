# An open library of metaheuristics for the unrelated parallel machines scheduling problem

This reproducible capsule contains 12 metaheuristics proposed for the Unrelated Parallel Machines Scheduling Problem (UPMSP) with setups and makespan minimization. The algorithms are based on the interpretation of the original papers according to the following list:

- **ALNS-TS**:  W. Fang, H. Zhu, Y. Mei, Hybrid meta-heuristics for the unrelated parallel machine scheduling problem with setup times, Knowledge-Based Systems 241 (2022) 108193. doi: 10.1016/j.knosys.2022.108193

- **FACL**: X. Huang, L. Chen, Y. Zhang, S. Su, Y. Lin, X. Cao, Improved firefly algorithm with courtship learning for unrelated parallel machine scheduling problem with sequence-dependent setup times, Journal of Cloud Computing 11 (2022). doi: 10.1186/s13677-022-00282-w.

- **FSS**: R. Jovanovic, S. Voß, Fixed set search application for minimizing the makespan on unrelated parallel machines with sequence-dependent setup times, Applied Soft Computing 110 (2021) 107521. doi: 10.1016/j.asoc.2021.107521.

- **GA**: E. Vallada, R. Ruiz, A genetic algorithm for the unrelated parallel machine scheduling problem with sequence dependent setup times, European Journal of Operational Research 211 (2011) 612–622. doi: 10.1016/j.ejor.2011.01.011.

- **GALA**: D. Y. Eroglu, H. C. Ozmutlu, S. Ozmutlu, Genetic algorithm with local search for the unrelated parallel machine scheduling problem with sequence-dependent set-up times, International Journal of Production Research 52 (2014) 5841–5856. doi: 10.1080/00207543.2014.920966.

- **HABC**: S. W. Lin, K. C. Ying, ABC-based manufacturing scheduling for unrelated parallel machines with machine-dependent and job sequence-dependent setup times, Computers & Operations Research 51 (2014) 172–181. doi: 10.1016/j.cor.2014.05.013. 

- **HGA**: J. Adan, A hybrid genetic algorithm for parallel machine scheduling with setup times, Journal of Intelligent Manufacturing 33 (2022) 2059–2073. doi: 10.1007/s10845-022-01959-4.

- **MSA**: O. Avalos-Rosales, F. Angel-Bello, A. Alvarez, Efficient metaheuristic algorithm and reformulations for the unrelated parallel machine scheduling problem with sequence and machine-dependent setup times, The International Journal of Advanced Manufacturing Technology 76 (2015) 1705–1718. doi: 10.1007/s00170-014-6390-6.

- **SA**: H. G. Santos, T. A. M. Toffolo, C. L. T. F. Silva, G. V. Berghe, Analysis of stochastic local search methods for the unrelated parallel machine scheduling problem, International Transactions in Operational Research 26 (2016) 707–724. doi: 10.1111/itor.12316.

- **SSAFA**: A. A. Ewees, M. A. A. Al-qaness, M. A. Elaziz, Enhanced salp swarm algorithm based on firefly algorithm for unrelated parallel machine scheduling with setup times, Applied Mathematical Modelling 94 (2021) 285–305. doi: 10.1016/j.apm.2021.01.017.

- **VNS-AiNet**: R. O. M. Diana, S. R. de Souza, E. F. Wanner, A robust multi-response VNS-aiNet approach for solving scheduling problems under unrelated parallel machines environments, Expert Systems with Applications 182 (2021) 115140. doi: 10.1016/j.eswa.2021.115140.

- **WOAFA**: M. A. A. Al-qaness, A. A. Ewees, M. A. Elaziz, Modified whale optimization algorithm for solving unrelated parallel machine scheduling problems, Soft Computing 25 (2021) 9545–9557. doi:10.1007/s00500-021-05889-w.

Dependencies: Julia version >= 1.4, DelimitedFiles, Distributions, Hungarian, Random, StatsBase. 

## Instance parameters

- _m_ (Int8): Number of machines
- _n_ (Int16): Number of jobs 
- _p_ (Matrix{Int16}): The matrix of processing times 
- _S_ (Vector{Matrix{Int16}}): A vector containing matrices of sequence-dependent setup times for each machine
- _t_ (Int8): The constant that defines the time limit of each execution.

## Metaheuristic parameters 

Each method is tuned according to the parameter values described in the original papers. 

## Run example

The example was taken from the benchmark of Vallada & Ruiz (2011): 

- _m_ = 2 
- _n_ = 6
- _p_ ~ _U_[1, 99]
- _S_ ~ _U_[1, 9]
- _t_ = 10

Optimal makespan (Cmax): 74.

The entire benchmark can be found [here](http://soa.iti.es).

## Output

Each metaheuristic should print the best value of the objective function, the number of iterations, and the number of objective function evaluations. 
