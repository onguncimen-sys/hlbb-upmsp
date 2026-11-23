include("Input.jl")
include("Modules.jl")

using .ALNS, .FACL, .FSS, .GA, .GALA, .HABC, .HGA, .MSA, .SA, .SSAFA, .VNSaiNet, .WOAFA

function Main_Metaheuristic()

    #----- The example of m = 2 and n = 6
    
    m::Int8 = 2 
    n::Int16 = 6
    t::Int8 = 10
    
    #----- Inputs the data from the example

    p, S = InputData(n, m)

    #----- Run the specified algorithm to solve the instance

    for i::Int8 in 1:12
        if i == 1
            OF, I, NI = Main_ALNS(m, n, p, S, t)
            println("Results ALNS: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 2
            OF, I, NI = Main_FACL(m, n, p, S, t)
            println("Results FACL: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 3
            OF, I, NI = Main_FSS(m, n, p, S, t)
            println("Results FSS: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 4
            OF, I, NI = Main_GA(m, n, p, S, t)
            println("Results GA: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 5
            OF, I, NI = Main_GALA(m, n, p, S, t)
            println("Results GALA: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 6 
            OF, I, NI = Main_HABC(m, n, p, S, t)
            println("Results HABC: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 7 
            OF, I, NI = Main_HGA(m, n, p, S, t)
            println("Results HGA: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 8 
            OF, I, NI = Main_MSA(m, n, p, S, t)
            println("Results MSA: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 9 
            OF, I, NI = Main_SA(m, n, p, S, t)
            println("Results SA: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 10 
            OF, I, NI = Main_SSAFA(m, n, p, S, t)
            println("Results SSAFA: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 11 
            OF, I, NI = Main_VNS(m, n, p, S, t)
            println("Results VNS-AiNet: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI\n*****")
        elseif i == 12 
            OF, I, NI = Main_WOAFA(m, n, p, S, t)
            println("Results WOAFA: \nBest Makespan: $OF\nIterations: $I\nObjective function evaluations: $NI")
        end
    end
end

Main_Metaheuristic()